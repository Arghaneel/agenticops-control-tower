"""Fleet acceptance: frozen scope, approvals, partial failure, restart and deadlines."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agenticops_control_tower.adapters.containment import SidecarContainmentAdapter
from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.api.http import create_app
from agenticops_control_tower.bulk import BulkRequest, BulkService
from agenticops_control_tower.cli.main import main
from agenticops_control_tower.config import (
    Configuration,
    ConfigurationError,
    ConfigurationService,
    Operator,
)
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.models import AgentRegistrationPayload, HeartbeatPayload
from agenticops_control_tower.registry import AgentRegistry

WRITER = Operator(operator_id="w", role="writer")
APPROVER = Operator(operator_id="p", role="approver")


def register(registry, aid, env="staging"):
    registry.register(
        AgentRegistrationPayload(
            agent_id=aid,
            name=aid,
            environment=env,
            runtime="local",
            framework="custom",
            capabilities={"agentic-sidecar": "0.8.0"},
        )
    )


@pytest.fixture
def service(tmp_path):
    path = str(tmp_path / "tower.db")
    registry = AgentRegistry(path)
    config = ConfigurationService(registry, path)
    for aid in ("b", "a", "production"):
        register(registry, aid, "production" if aid == "production" else "staging")
        config.declare(
            Configuration(agent_id=aid, capability="agentic-sidecar", authority="tower"), WRITER
        )
    return BulkService(config)


def request(operation="config.update", **kwargs):
    return BulkRequest(
        intent="Enable staging diagnostics",
        selector={"environment": "staging", "capability": "agentic-sidecar"},
        operation=operation,
        patch={"values": {"tracing": True}} if operation == "config.update" else {},
        **kwargs,
    )


def approved(service, req=None):
    action = service.preview(req or request(), WRITER)
    service.decide(action.bulk_id, True, APPROVER)
    return action.bulk_id


def test_frozen_scope_restart_and_partial_failure(service):
    bid = approved(service)
    register(service.config.registry, "new")
    service.config.declare(service.config.get("b", "agentic-sidecar"), WRITER)
    restored = BulkService(ConfigurationService(service.config.registry, service.config._path))
    result = restored.execute(bid, WRITER)
    assert [(r.agent_id, r.outcome) for r in result.targets] == [
        ("a", "succeeded"),
        ("b", "failed"),
    ]
    assert restored.config.get("a", "agentic-sidecar").values == {"tracing": True}
    assert restored.config.get("b", "agentic-sidecar").values == {}
    assert restored.config.get("production", "agentic-sidecar").values == {}
    assert result.events[-1].event == "bulk.completed"
    assert any(r.action_id == bid for r in restored.config.audit("a"))
    with pytest.raises(ConfigurationError):
        restored.execute(bid, WRITER)
    for target in result.targets:
        with pytest.raises(ConfigurationError):
            restored.config.action(target.preview.action_id)


@pytest.mark.parametrize("state", ["pending", "denied", "revoked", "expired"])
def test_invalid_approval(service, state):
    action = service.preview(request(), WRITER)
    if state == "denied":
        service.decide(action.bulk_id, False, APPROVER)
    elif state != "pending":
        service.decide(action.bulk_id, True, APPROVER)
        if state == "revoked":
            service.revoke(action.bulk_id, APPROVER)
        else:
            with service.config._transaction() as db:
                action = service._load(db, action.bulk_id)
                action.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                service._save(db, action)
    with pytest.raises(ConfigurationError):
        service.execute(action.bulk_id, WRITER)
    assert service.config.get("a", "agentic-sidecar").values == {}


def test_authorization_and_detached_reads(service):
    action = service.preview(request(), WRITER)
    for method in (service.preview,):
        with pytest.raises(ConfigurationError):
            method(request(), APPROVER)
    for operator in (
        WRITER,
        Operator(operator_id="w", role="approver"),
        APPROVER.model_copy(update={"agent_ids": ["a"]}),
    ):
        with pytest.raises(ConfigurationError):
            service.decide(action.bulk_id, True, operator)
    with pytest.raises(ConfigurationError):
        service.get(action.bulk_id, WRITER.model_copy(update={"agent_ids": []}))
    action.request.patch.values["tracing"] = False
    service.decide(action.bulk_id, True, APPROVER)
    result = service.execute(action.bulk_id, WRITER)
    assert result.targets[0].preview.after.values == {"tracing": True}


def test_selectors_and_changed_deployment(service):
    for ids in (["a", "missing"], ["production"]):
        req = request()
        req.selector.agent_ids = ids
        with pytest.raises(ConfigurationError):
            service.preview(req, WRITER)
    req = request()
    req.selector.environment = "absent"
    with pytest.raises(ConfigurationError):
        service.preview(req, WRITER)
    bid = approved(service)
    service.config.registry.heartbeat(
        "a", HeartbeatPayload(capabilities={"agentic-sidecar": "0.9"})
    )
    register(service.config.registry, "b", "production")
    assert [t.outcome for t in service.execute(bid, WRITER).targets] == ["failed", "failed"]


def test_concurrent_claim(service):
    bid = approved(service)

    def execute(_):
        try:
            return service.execute(bid, WRITER).status
        except ConfigurationError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(execute, range(2))) == ["completed", "rejected"]


class Runtime:
    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, 0
        self.release = Event()

    def control(self, action, actor):
        self.calls += 1
        if self.mode == "wait":
            self.release.wait(5)
        if self.mode == "error":
            raise RuntimeError("secret must not persist")
        return {
            "action": action,
            "running": ["call"] if self.mode == "running" else [],
            "revocations": {} if self.mode == "unsupported" else {"mcp": True},
            "access_revocation": "acknowledged",
        }


@pytest.mark.parametrize(
    "mode,outcome",
    [
        ("ok", "acknowledged"),
        ("wait", "timed_out"),
        ("error", "failed"),
        ("running", "incomplete"),
        ("unsupported", "unsupported"),
    ],
)
def test_stop_receipts_deadline_and_no_replay(service, mode, outcome):
    runtime = Runtime(mode)
    service.install("a", SidecarContainmentAdapter(runtime))
    # Only "wait" should miss the deadline; a 10 ms budget for the immediate modes
    # times out on slow CI runners before the dispatch thread is even scheduled.
    seconds = 0.01 if mode == "wait" else 5
    bid = approved(service, request("runtime.stop", acknowledgement_seconds=seconds))
    try:
        result = service.execute(bid, WRITER)
        assert [t.outcome for t in result.targets] == [outcome, "unsupported"]
        assert runtime.calls == 1
        assert "secret" not in result.model_dump_json()
        assert "downstream" in result.reconciliation
        with pytest.raises(ConfigurationError):
            service.execute(bid, WRITER)
        assert runtime.calls == 1
    finally:
        runtime.release.set()


def test_interrupted_execution_readback(service):
    bid = approved(service, request("runtime.stop"))
    with service.config._transaction() as db:
        action = service._load(db, bid)
        action.status = "executing"
        action.targets[0].outcome = "requested"
        service._save(db, action)
    restored = BulkService(ConfigurationService(service.config.registry, service.config._path))
    assert restored.get(bid, WRITER).targets[0].outcome == "requested"
    with pytest.raises(ConfigurationError):
        restored.execute(bid, WRITER)


def test_http_cli_and_snapshot_rejection(service, tmp_path, capsys):
    api = ControlTowerAPI(
        service.config.registry, CapabilityDiscoveryService(), configuration_service=service.config
    )
    client = TestClient(create_app(api, read_token="r", write_token="w", approval_token="p"))
    payload = tmp_path / "bulk.json"
    payload.write_text(request().model_dump_json())
    assert client.post("/bulk/preview", json=request().model_dump()).status_code == 401
    with pytest.raises(SystemExit, match="409"):
        main(["--token", "r", "bulk", "preview", str(payload)], client=client)
    capsys.readouterr()
    assert main(["--token", "w", "bulk", "preview", str(payload)], client=client) == 0
    bid = json.loads(capsys.readouterr().out)["bulk_id"]
    assert main(["--token", "p", "bulk", "approve", bid], client=client) == 0
    capsys.readouterr()
    assert main(["--token", "w", "bulk", "execute", bid], client=client) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    assert (
        client.post(f"/bulk/{bid}/execute", headers={"Authorization": "Bearer w"}).status_code
        == 409
    )
    assert client.get(f"/bulk/{bid}", headers={"Authorization": "Bearer r"}).status_code == 200
    with pytest.raises(SystemExit):
        main(
            ["--snapshot", "examples/sample_fleet_snapshot.json", "bulk", "get", bid], client=client
        )


def test_limits_and_toggle(service):
    for changes in ({"acknowledgement_seconds": float("nan")}, {"expires_in_seconds": 0}):
        with pytest.raises(ValidationError):
            request(**changes)
    with pytest.raises(ValidationError):
        BulkRequest(
            intent="x",
            selector={"environment": "staging", "capability": "x"},
            operation="runtime.stop",
            patch={"values": {"x": True}},
        )
    bid = approved(service, request("capabilities.disable"))
    assert all(t.outcome == "succeeded" for t in service.execute(bid, WRITER).targets)
    assert service.config.get("a", "agentic-sidecar").enabled is False


def test_actual_sidecar_stop(service):
    sidecar = pytest.importorskip("agentic_sidecar")
    runtime = sidecar.TaskRuntime(
        task_id="bulk-test", revokers={"mcp": lambda task: task == "bulk-test"}
    )
    sidecar.Sidecar(on_sidecar_failure="fail_closed", runtime=runtime)
    service.install("a", SidecarContainmentAdapter(runtime))
    result = service.execute(approved(service, request("runtime.stop")), WRITER)
    assert result.targets[0].outcome == "acknowledged"
    assert result.targets[0].receipt["mcp_revocation"] == "acknowledged"


def test_preview_transaction_rolls_back_all_children(service):
    service.config.declare(
        Configuration(agent_id="b", capability="agentic-sidecar", authority="mirrored"), WRITER
    )
    with pytest.raises(ConfigurationError):
        service.preview(request(), WRITER)
    with service.config._transaction(write=False) as db:
        assert db.execute("SELECT count(*) FROM tower_bulk").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM tower_actions").fetchone()[0] == 0
    assert service.config.get("a", "agentic-sidecar").values == {}


def test_capacity_exhaustion_does_not_dispatch(service, monkeypatch):
    from agenticops_control_tower.bulk import service as bulk_module

    class Full:
        def acquire(self, blocking):
            return False

    monkeypatch.setattr(bulk_module, "_DISPATCH_SLOTS", Full())
    runtime = Runtime()
    service.install("a", SidecarContainmentAdapter(runtime))
    result = service.execute(approved(service, request("runtime.stop")), WRITER)
    assert result.targets[0].outcome == "failed"
    assert runtime.calls == 0


def test_target_limit(service):
    for number in range(100):
        register(service.config.registry, f"extra-{number}")
    with pytest.raises(ConfigurationError, match="100"):
        service.preview(request("runtime.stop"), WRITER)


def test_example_runs():
    import runpy

    runpy.run_path("examples/fleet_operations.py", run_name="__main__")


def test_late_receipt_is_durable_without_changing_timeout(service, monkeypatch):
    runtime = Runtime("wait")
    receipt_saved = Event()
    original = service._event

    def event(action, name, operator, agent_id=None):
        original(action, name, operator, agent_id)
        if name == "target.receipt_received":
            receipt_saved.set()

    monkeypatch.setattr(service, "_event", event)
    service.install("a", SidecarContainmentAdapter(runtime))
    bid = approved(service, request("runtime.stop", acknowledgement_seconds=0.01))
    result = service.execute(bid, WRITER)
    assert result.targets[0].outcome == "timed_out"
    runtime.release.set()
    assert receipt_saved.wait(2)
    restored = BulkService(ConfigurationService(service.config.registry, service.config._path))
    target = restored.get(bid, WRITER).targets[0]
    assert target.outcome == "timed_out"
    assert target.receipt["outcome"] == "acknowledged"
    audit = restored.config.audit("a")
    assert any(
        r.event == "bulk.target.receipt_received" and '"mcp_revocation"' in r.detail for r in audit
    )


def test_batch_deadline_skips_remaining_dispatches(service):
    runtime = Runtime("wait")
    service.install("a", SidecarContainmentAdapter(runtime))
    service.install("b", SidecarContainmentAdapter(runtime))
    bid = approved(
        service, request("runtime.stop", execution_seconds=0.01, acknowledgement_seconds=30)
    )
    try:
        result = service.execute(bid, WRITER)
        assert [t.outcome for t in result.targets] == ["timed_out", "failed"]
        assert "deadline" in result.targets[1].detail
        assert runtime.calls == 1
    finally:
        runtime.release.set()


def test_configuration_audit_references_durable_batch(service):
    bid = approved(service)
    service.execute(bid, WRITER)
    for aid in ("a", "b"):
        records = [r for r in service.config.audit(aid) if r.action_id]
        assert records and {r.action_id for r in records} == {bid}
        assert service.get(bid, WRITER).targets[0].preview.status == "executed"
