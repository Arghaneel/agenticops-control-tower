"""Approval safety, persistence, concurrency, ownership and HTTP acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.api.http import create_app
from agenticops_control_tower.config import (
    ActionRequest,
    Configuration,
    ConfigurationError,
    ConfigurationService,
    Operator,
)
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.models import AgentRegistrationPayload
from agenticops_control_tower.registry import AgentRegistry

WRITER = Operator(operator_id="operator", role="writer")
APPROVER = Operator(operator_id="reviewer", role="approver")


@pytest.fixture
def service(tmp_path):
    path = str(tmp_path / "tower.db")
    registry = AgentRegistry(path)
    registry.register(
        AgentRegistrationPayload(
            agent_id="a",
            name="A",
            environment="staging",
            runtime="custom",
            framework="custom",
        )
    )
    service = ConfigurationService(registry, path)
    service.declare(
        Configuration(
            agent_id="a",
            capability="routing",
            authority="tower",
            reason="Tower desired routing settings",
        ),
        WRITER,
    )
    return service


def request(operation="config.update"):
    return ActionRequest(
        target={"agent_id": "a", "capability": "routing", "environment": "staging"},
        operation=operation,
        patch={"values": {"limit": 5}} if operation == "config.update" else {},
    )


def test_persistence_and_single_use(service):
    action = service.preview(request(), WRITER)
    action.after.values["limit"] = 999  # Returned previews cannot modify stored approvals.
    service.approve(action.action_id, True, APPROVER)
    restored = ConfigurationService(service.registry, service._path)
    result = restored.execute(action.action_id, WRITER)
    assert result.configuration.values == {"limit": 5}
    assert result.rollback == "not_needed"
    with pytest.raises(ConfigurationError):
        restored.execute(action.action_id, WRITER)
    assert [r.event for r in restored.audit("a")] == [
        "configuration.declared",
        "action.previewed",
        "action.approved",
        "action.executed",
        "action.rejected",
    ]


@pytest.mark.parametrize("state", ["pending", "denied", "revoked", "expired", "stale"])
def test_invalid_approval_cannot_execute(service, state):
    action = service.preview(request(), WRITER)
    if state == "denied":
        service.approve(action.action_id, False, APPROVER)
    elif state != "pending":
        service.approve(action.action_id, True, APPROVER)
        if state == "revoked":
            service.revoke(action.action_id, APPROVER)
        elif state == "expired":
            with service._transaction() as db:
                stored = service._action(db, action.action_id)
                stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                service._save_action(db, stored)
        else:
            service.declare(service.get("a", "routing"), WRITER)
    with pytest.raises(ConfigurationError):
        service.execute(action.action_id, WRITER)
    assert service.get("a", "routing").values == {}


def test_roles_scope_ownership_and_environment(service):
    with pytest.raises(ConfigurationError):
        service.preview(request(), Operator(operator_id="x", role="writer", agent_ids=[]))
    action = service.preview(request(), WRITER)
    with pytest.raises(ConfigurationError):
        service.approve(action.action_id, True, WRITER.model_copy(update={"role": "approver"}))
    service.declare(Configuration(agent_id="a", capability="routing", authority="mirrored"), WRITER)
    with pytest.raises(ConfigurationError):
        service.preview(request(), WRITER)
    assert service.get("a", "agentic-sidecar").authority == "unsupported"
    wrong = request()
    wrong.target.environment = "production"
    with pytest.raises(ConfigurationError):
        service.preview(wrong, WRITER)


def test_competing_actions_and_toggles(service):
    actions = [service.preview(request("capabilities.disable"), WRITER) for _ in range(2)]
    for action in actions:
        service.approve(action.action_id, True, APPROVER)

    def execute(action):
        try:
            return service.execute(action.action_id, WRITER).outcome
        except ConfigurationError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(execute, actions)) == ["rejected", "succeeded"]
    assert service.get("a", "routing").enabled is False
    action = service.preview(request("capabilities.enable"), WRITER)
    service.approve(action.action_id, True, APPROVER)
    assert service.execute(action.action_id, WRITER).configuration.enabled is True


def test_http_authorization(service):
    api = ControlTowerAPI(
        service.registry, CapabilityDiscoveryService(), configuration_service=service
    )
    client = TestClient(create_app(api, read_token="r", write_token="w", approval_token="p"))

    def headers(token):
        return {"Authorization": f"Bearer {token}"}

    assert client.post("/actions/preview", json=request().model_dump()).status_code == 401
    assert (
        client.post(
            "/actions/preview", json=request().model_dump(), headers=headers("r")
        ).status_code
        == 409
    )
    action = client.post(
        "/actions/preview", json=request().model_dump(), headers=headers("w")
    ).json()
    aid = action["action_id"]
    assert (
        client.post(
            f"/actions/{aid}/approval", json={"approved": True}, headers=headers("w")
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/actions/{aid}/approval", json={"approved": True}, headers=headers("p")
        ).status_code
        == 200
    )
    assert client.post(f"/actions/{aid}/execute", headers=headers("p")).status_code == 409
    assert client.post(f"/actions/{aid}/execute", headers=headers("w")).status_code == 200
    assert client.get("/agents/a/config/routing", headers=headers("r")).json()["values"] == {
        "limit": 5
    }
    assert len(client.get("/agents/a/audit", headers=headers("r")).json()) == 7
    with pytest.raises(ValueError):
        create_app(write_token="w", approval_token="w")


def test_storage_failure_rolls_back_configuration_and_approval(service):
    import sqlite3

    action = service.preview(request(), WRITER)
    service.approve(action.action_id, True, APPROVER)
    with service._transaction() as db:
        db.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON tower_audit "
            "BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        service.execute(action.action_id, WRITER)
    assert service.get("a", "routing").values == {}
    assert service.action(action.action_id).status == "approved"
    with service._transaction() as db:
        db.execute("DROP TRIGGER fail_audit")
    assert service.execute(action.action_id, WRITER).outcome == "succeeded"


def test_cli_approval_flow(service, tmp_path, capsys):
    import json

    from agenticops_control_tower.cli.main import main

    api = ControlTowerAPI(
        service.registry, CapabilityDiscoveryService(), configuration_service=service
    )
    client = TestClient(create_app(api, write_token="w", approval_token="p"))
    payload = tmp_path / "request.json"
    payload.write_text(request().model_dump_json())
    main(["--token", "w", "actions", "preview", str(payload)], client=client)
    action_id = json.loads(capsys.readouterr().out)["action_id"]
    main(["--token", "p", "actions", "get", action_id], client=client)
    assert json.loads(capsys.readouterr().out)["status"] == "pending"
    main(["--token", "p", "actions", "approve", action_id], client=client)
    assert json.loads(capsys.readouterr().out)["status"] == "approved"
    main(["--token", "w", "actions", "execute", action_id], client=client)
    assert json.loads(capsys.readouterr().out)["outcome"] == "succeeded"
    main(["--token", "w", "config", "a", "routing"], client=client)
    assert json.loads(capsys.readouterr().out)["values"] == {"limit": 5}
    main(["--token", "w", "audit", "a"], client=client)
    assert json.loads(capsys.readouterr().out)[-1]["event"] == "action.executed"


def test_target_schema_and_empty_environment(service):
    from pydantic import ValidationError

    for target in (
        {"agent_id": "a"},
        {"agent_id": "a", "capability": ""},
        {"agent_id": "a", "capability": "namespace/routing"},
    ):
        with pytest.raises(ValidationError):
            ActionRequest(target=target, operation="config.update")
    action_request = request()
    action_request.target.environment = ""
    with pytest.raises(ConfigurationError):
        service.preview(action_request, WRITER)
    agent = service.registry.get("a")
    agent.environment = ""
    service.registry.register(AgentRegistrationPayload.model_validate(agent.model_dump()))
    action = service.preview(action_request, WRITER)
    service.approve(action.action_id, True, APPROVER)
    agent.environment = "production"
    service.registry.register(AgentRegistrationPayload.model_validate(agent.model_dump()))
    with pytest.raises(ConfigurationError):
        service.execute(action.action_id, WRITER)


def test_denial_attribution(service):
    action = service.preview(request(), WRITER)
    denied = service.approve(action.action_id, False, APPROVER)
    assert denied.approved_by is None
    assert denied.decided_by == APPROVER.operator_id


def test_reads_do_not_reserve_sqlite_writer_lock(service):
    import sqlite3

    competitor = sqlite3.connect(service._path, timeout=0)
    try:
        with service._transaction(write=False) as db:
            db.execute("SELECT body FROM tower_config").fetchall()
            competitor.execute("BEGIN IMMEDIATE")
            competitor.rollback()
    finally:
        competitor.close()
