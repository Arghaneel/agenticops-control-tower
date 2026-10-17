"""Real service/HTTP transitions and crash-safe approval boundaries."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.api.http import create_app
from agenticops_control_tower.config.models import Operator
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.evidence import EvidenceStore
from agenticops_control_tower.incidents import IncidentError, IncidentService
from agenticops_control_tower.incidents.staging import StagingDependencyRuntime
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.models.evidence import EvidenceLink
from agenticops_control_tower.registry import AgentRegistry

WRITER = Operator(operator_id="operator", role="writer")
APPROVER = Operator(operator_id="human", role="approver")
READER = Operator(operator_id="reader", role="reader")


def evidence(store, source="agenticlens", status="failed", run_id="failure", observed_at=None):
    now = observed_at or datetime.now(timezone.utc)
    if source == "agenticlens":
        artifact = dict(
            schema_version="1.0",
            run_id=run_id,
            application_name="staging",
            status=status,
            task_success=status == "succeeded",
            trace_id="trace:" + run_id,
            error_type="ConnectionError" if status == "failed" else None,
            spans=[
                dict(
                    span_id="tool",
                    name="dependency call",
                    span_type="tool",
                    tool_name="search",
                    status=status,
                    error_type="ConnectionError" if status == "failed" else None,
                )
            ],
        )
    else:
        artifact = dict(
            schema_version="1.0",
            suite_name="recovery",
            suite_version="1",
            created_at=now.isoformat(),
            summary=dict(
                total_cases=1, passed_cases=1, failed_cases=0, pass_rate=1.0, average_score=1.0
            ),
        )
    request = EvidenceIngestRequest(
        link=EvidenceLink(
            agent_id="staging",
            source=source,
            source_version="0.7.1",
            artifact_type="run" if source == "agenticlens" else "evaluation_report",
            artifact_ref=source + ":" + run_id + ":" + status,
            observed_at=now,
            run_id=run_id,
        ),
        artifact=artifact,
        gate=dict(passed=status == "succeeded", reasons=[], observed={})
        if source == "agentic-evals"
        else None,
    )
    return store.ingest(request).record


@pytest.fixture
def setup(tmp_path):
    path = str(tmp_path / "tower.sqlite")
    registry = AgentRegistry(path)
    registry.register(
        AgentRegistrationPayload(
            agent_id="staging",
            name="staging",
            environment="staging",
            runtime="fixture",
            framework="custom",
        )
    )
    store = EvidenceStore(registry, path)
    runtime = StagingDependencyRuntime(str(tmp_path / "runtime.sqlite"), "staging", "search")
    runtime.fail()
    service = IncidentService(registry, store, path, {"staging": runtime})
    return registry, store, service, runtime, path


def planned(setup):
    _, store, service, _, _ = setup
    record = evidence(store)
    incident = service.detect("staging", record.record_id, WRITER)
    service.investigate(incident.incident_id, WRITER)
    return service.preview(incident.incident_id, "search", 300, WRITER)


def test_success_requires_probe_and_fresh_correlated_evidence(setup):
    _, store, service, runtime, _ = setup
    incident = planned(setup)
    assert incident.investigation.certainty == "hypothesis"
    assert incident.detection.record_id in incident.investigation.citations
    service.decide(incident.incident_id, incident.preview_digest, True, APPROVER)
    executed = service.execute(incident.incident_id, incident.preview_digest, WRITER)
    assert executed.state == "awaiting_verification"
    lens = evidence(store, status="succeeded", run_id="recovery")
    evals = evidence(store, "agentic-evals", "succeeded", "recovery")
    result = service.verify(incident.incident_id, lens.record_id, evals.record_id, WRITER)
    assert result.state == "resolved"
    assert runtime.probe(incident.plan)
    assert result.events[-1].event == "verification.resolved"


@pytest.mark.parametrize(
    "failure", ["denied", "revoked", "digest", "scope", "role", "self", "expired"]
)
def test_rejected_approval_never_dispatches(setup, failure):
    _, _, service, runtime, path = setup
    incident = planned(setup)
    iid, digest = incident.incident_id, incident.preview_digest
    if failure == "self":
        with pytest.raises(IncidentError):
            service.decide(iid, digest, True, Operator(operator_id="operator", role="approver"))
    elif failure == "expired":
        with sqlite3.connect(path) as db:
            incident.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            service._save(db, incident)
        with pytest.raises(IncidentError):
            service.decide(iid, digest, True, APPROVER)
    else:
        service.decide(iid, digest, failure != "denied", APPROVER)
        if failure == "revoked":
            service.revoke(iid, APPROVER)
    operator = (
        Operator(operator_id="scoped", role="writer", agent_ids=[])
        if failure == "scope"
        else READER
        if failure == "role"
        else WRITER
    )
    with pytest.raises(IncidentError):
        service.execute(iid, "modified" if failure == "digest" else digest, operator)
    assert not runtime.probe(incident.plan)


def test_duplicate_execution_across_process_services(setup):
    registry, store, service, runtime, path = setup
    incident = planned(setup)
    service.decide(incident.incident_id, incident.preview_digest, True, APPROVER)
    second = IncidentService(registry, store, path, {"staging": runtime})

    def execute(s):
        try:
            return s.execute(incident.incident_id, incident.preview_digest, WRITER).state
        except IncidentError:
            return "rejected"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(execute, [service, second]))
    assert sorted(results) == ["awaiting_verification", "rejected"]
    with sqlite3.connect(runtime.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM staging_receipts").fetchone()[0] == 1
    assert second.get(incident.incident_id, READER).approval == "consumed"


@pytest.mark.parametrize("failure", ["stale", "wrong_run", "gate", "probe", "future"])
def test_failed_verification_escalates(setup, failure):
    _, store, service, runtime, _ = setup
    incident = planned(setup)
    service.decide(incident.incident_id, incident.preview_digest, True, APPROVER)
    service.execute(incident.incident_id, incident.preview_digest, WRITER)
    observed = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
        if failure == "stale"
        else datetime.now(timezone.utc) + timedelta(seconds=30)
        if failure == "future"
        else None
    )
    lens = evidence(store, status="succeeded", run_id="recovery", observed_at=observed)
    evals = evidence(
        store,
        "agentic-evals",
        "failed" if failure == "gate" else "succeeded",
        "other" if failure == "wrong_run" else "recovery",
    )
    if failure == "probe":
        runtime.fail()
    assert (
        service.verify(incident.incident_id, lens.record_id, evals.record_id, WRITER).state
        == "escalated"
    )


def test_partial_execution_and_crash_are_not_replayed(setup, monkeypatch):
    registry, store, service, runtime, path = setup
    incident = planned(setup)
    service.decide(incident.incident_id, incident.preview_digest, True, APPROVER)

    def crash(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(runtime, "execute", crash)
    with pytest.raises(KeyboardInterrupt):
        service.execute(incident.incident_id, incident.preview_digest, WRITER)
    restarted = IncidentService(registry, store, path, {"staging": runtime})
    result = restarted.get(incident.incident_id, READER)
    assert result.state == "executing" and result.outcome == "unknown"
    assert restarted.reconcile(incident.incident_id, WRITER).state == "escalated"
    with pytest.raises(IncidentError):
        restarted.execute(incident.incident_id, incident.preview_digest, WRITER)


def test_contradictory_evidence_prevents_plan(setup):
    _, store, service, _, _ = setup
    record = evidence(store)
    incident = service.detect("staging", record.record_id, WRITER)
    evidence(store, status="succeeded", run_id="failure")
    assert (
        service.investigate(incident.incident_id, WRITER).investigation.certainty == "contradictory"
    )
    with pytest.raises(IncidentError):
        service.preview(incident.incident_id, "search", 300, WRITER)
    assert service.detect("staging", record.record_id, WRITER).incident_id == incident.incident_id


def test_http_end_to_end_and_roles(setup):
    registry, store, service, _, _ = setup
    api = ControlTowerAPI(
        registry, CapabilityDiscoveryService(), evidence_store=store, incident_service=service
    )
    client = TestClient(
        create_app(api, read_token="read", write_token="write", approval_token="approve")
    )
    record = evidence(store)
    writer = {"Authorization": "Bearer write"}
    approver = {"Authorization": "Bearer approve"}
    reader = {"Authorization": "Bearer read"}
    payload = {"agent_id": "staging", "evidence_id": record.record_id}
    assert client.post("/incidents/detect", json=payload).status_code == 401
    assert client.post("/incidents/detect", json=payload, headers=reader).status_code == 409
    incident = client.post("/incidents/detect", json=payload, headers=writer).json()
    base = "/incidents/" + incident["incident_id"]
    assert client.post(base + "/investigate", headers=writer).status_code == 200
    preview = client.post(base + "/preview", json={"dependency": "search"}, headers=writer).json()
    digest = {"preview_digest": preview["preview_digest"]}
    assert (
        client.post(
            base + "/approval", json={**digest, "approved": True}, headers=writer
        ).status_code
        == 409
    )
    assert (
        client.post(
            base + "/approval", json={**digest, "approved": True}, headers=approver
        ).status_code
        == 200
    )
    assert (
        client.post(base + "/execute", json=digest, headers=writer).json()["state"]
        == "awaiting_verification"
    )
    lens = evidence(store, status="succeeded", run_id="recovery")
    evals = evidence(store, "agentic-evals", "succeeded", "recovery")
    result = client.post(
        base + "/verify",
        json={"lens_evidence_id": lens.record_id, "evals_evidence_id": evals.record_id},
        headers=writer,
    )
    assert result.json()["state"] == "resolved"
    assert client.get(base, headers=reader).json()["state"] == "resolved"


def test_cli_reads_incidents_and_rejects_offline_writes(setup, capsys):
    from agenticops_control_tower.cli.main import main

    registry, store, service, _, _ = setup
    incident = planned(setup)
    api = ControlTowerAPI(
        registry, CapabilityDiscoveryService(), evidence_store=store, incident_service=service
    )
    client = TestClient(create_app(api, read_token="reader"))
    assert main(["--token", "reader", "incidents", "list"], client=client) == 0
    assert incident.incident_id in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--snapshot", "unused.json", "incidents", "list"])


def test_connector_failure_escalates_with_reconciliation(setup, monkeypatch):
    _, _, service, runtime, _ = setup
    incident = planned(setup)
    service.decide(incident.incident_id, incident.preview_digest, True, APPROVER)

    def fail(*args):
        raise TimeoutError("runtime timeout")

    monkeypatch.setattr(runtime, "execute", fail)
    result = service.execute(incident.incident_id, incident.preview_digest, WRITER)
    assert result.state == "escalated" and result.outcome == "partial_failure"
    assert "Reconcile" in result.events[-1].detail


def test_runtime_lock_timeout_is_bounded(setup):
    _, _, service, runtime, _ = setup
    incident = planned(setup)
    plan = incident.plan.model_copy(update={"timeout_seconds": 1})
    with sqlite3.connect(runtime.database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            runtime.execute(incident.incident_id, plan)
    assert not runtime.probe(plan)


def test_scope_restrictions_and_missing_connector(setup):
    _, store, service, _, _ = setup
    incident = planned(setup)
    with pytest.raises(IncidentError):
        service.get(
            incident.incident_id, Operator(operator_id="other", role="reader", agent_ids=[])
        )
    assert service.list(Operator(operator_id="other", role="reader", agent_ids=[])) == []
    assert len(service.list(READER)) == 1
    service.decide(incident.incident_id, incident.preview_digest, True, APPROVER)
    service.connectors.clear()
    with pytest.raises(IncidentError):
        service.execute(incident.incident_id, incident.preview_digest, WRITER)
    assert service.get(incident.incident_id, READER).approval == "approved"
    with pytest.raises(ValueError):
        service.detect("staging", "not-an-evidence-id", WRITER)
    success = evidence(store, status="succeeded", run_id="unrelated")
    with pytest.raises(IncidentError):
        service.detect("staging", success.record_id, WRITER)


def test_containment_adapter_delegates_stop_and_explicit_restart(setup):
    from agenticops_control_tower.adapters.containment import (
        MCPAccessRevoker,
        SidecarContainmentAdapter,
    )

    class Issuer:
        active = True

        def authenticate(self, token):
            return "user" if self.active else None

        def revoke(self, user, token):
            self.active = False

    issuer = Issuer()
    revoker = MCPAccessRevoker(issuer, "task", "user", "secret")
    assert not revoker("wrong-task")
    assert revoker("task") and revoker("task")

    class Runtime:
        calls = []

        def control(self, action, actor):
            self.calls.append((action, actor))
            return {
                "action": action,
                "running": [],
                "revocations": {"mcp": True},
                "access_revocation": "acknowledged",
            }

    _, _, service, _, _ = setup
    incident = planned(setup)
    runtime = Runtime()
    service.containment["staging"] = SidecarContainmentAdapter(runtime)
    result = service.control(incident.incident_id, "stop", WRITER)
    assert result.events[-1].event == "control.stop.acknowledged"
    assert "boundary_acknowledged" in result.events[-1].detail
    assert "secret" not in result.model_dump_json()
    service.control(incident.incident_id, "restart", WRITER)
    assert runtime.calls == [("stop", "operator"), ("restart", "operator")]


def test_actual_sidecar_stop_blocks_dispatch(setup):
    sidecar = pytest.importorskip("agentic_sidecar")
    from agenticops_control_tower.adapters.containment import SidecarContainmentAdapter

    runtime = sidecar.TaskRuntime(task_id="tower-test", revokers={"mcp": lambda task: True})
    supervisor = sidecar.Sidecar(runtime=runtime, on_sidecar_failure="fail_closed")
    from agentic_sidecar.core.context import DecisionContext
    from agentic_sidecar.core.exceptions import SidecarBlockedError

    context = DecisionContext(tool_name="search")
    decision = supervisor.evaluate(context)
    _, _, service, _, _ = setup
    incident = planned(setup)
    service.containment["staging"] = SidecarContainmentAdapter(runtime)
    result = service.control(incident.incident_id, "stop", WRITER)
    assert runtime.stopped
    with pytest.raises(SidecarBlockedError):
        runtime.dispatch(context, decision)
    assert "boundary_acknowledged" in result.events[-1].detail
    service.control(incident.incident_id, "restart", WRITER)
    assert not runtime.stopped


def test_mcp_dispatch_over_live_tower_api(setup, monkeypatch):
    import asyncio
    import json
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    mcp = pytest.importorskip("deep_agentic_core_mcp.server")
    if "tower.detect" not in mcp._TOOL_DISPATCH:
        pytest.skip("MCP >=0.3.6 connector required")
    registry, store, service, _, _ = setup
    api = ControlTowerAPI(
        registry, CapabilityDiscoveryService(), evidence_store=store, incident_service=service
    )
    app = create_app(api, read_token="r", write_token="w", approval_token="a")
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    monkeypatch.delenv("DEEP_AGENTIC_CORE_MCP_REMOTE", raising=False)
    monkeypatch.setenv("AGENTICOPS_TOWER_URL", origin)
    monkeypatch.setenv("AGENTICOPS_TOWER_READ_TOKEN", "r")
    monkeypatch.setenv("AGENTICOPS_TOWER_WRITE_TOKEN", "w")
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()

    def call(name, args):
        result = asyncio.run(mcp.handle_call_tool("tower." + name, args))
        payload = json.loads(result[0].text)
        assert payload["ok"], payload
        return payload["data"]

    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.01)
        assert server.started
        failed = evidence(store)
        incident = call("detect", {"agent_id": "staging", "evidence_id": failed.record_id})
        iid = {"incident_id": incident["incident_id"]}
        call("investigate", iid)
        preview = call("preview", {**iid, "dependency": "search"})
        digest = {"preview_digest": preview["preview_digest"]}
        with httpx.Client(base_url=origin) as client:
            approval = client.post(
                "/incidents/" + iid["incident_id"] + "/approval",
                json={**digest, "approved": True},
                headers={"Authorization": "Bearer a"},
            )
            approval.raise_for_status()
        assert call("execute", {**iid, **digest})["state"] == "awaiting_verification"
        lens = evidence(store, status="succeeded", run_id="mcp-recovery")
        evals = evidence(store, "agentic-evals", "succeeded", "mcp-recovery")
        assert (
            call(
                "verify",
                {**iid, "lens_evidence_id": lens.record_id, "evals_evidence_id": evals.record_id},
            )["state"]
            == "resolved"
        )
        assert call("incident", iid)["state"] == "resolved"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
