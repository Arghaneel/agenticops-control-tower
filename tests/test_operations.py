"""Live detection boundaries, persistent alerts and joined operator evidence."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.api.http import create_app
from agenticops_control_tower.config.models import Configuration, Operator
from agenticops_control_tower.config.service import ConfigurationService
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.evidence import EvidenceStore
from agenticops_control_tower.incidents import IncidentError, IncidentService
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.operations.models import DetectionPolicy
from agenticops_control_tower.registry import AgentRegistry
from test_incidents import READER, WRITER, evidence


@pytest.fixture
def tower(tmp_path):
    path = str(tmp_path / "live.sqlite")
    registry = AgentRegistry(path)
    registry.register(
        AgentRegistrationPayload(
            agent_id="staging",
            name="Staging",
            environment="staging",
            runtime="custom",
            framework="custom",
            status="healthy",
            capabilities={"agenticlens": "0.10.0"},
        )
    )
    store = EvidenceStore(registry, path)
    api = ControlTowerAPI(
        registry,
        CapabilityDiscoveryService(),
        evidence_store=store,
        incident_service=IncidentService(registry, store, path),
        configuration_service=ConfigurationService(registry, path),
    )
    return api, path


def test_fresh_failure_is_durable_deduplicated_and_acknowledged(tower):
    api, path = tower
    record = evidence(api.evidence)
    alerts = api.operations.evaluate(WRITER)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule == "lens.failed" and alert.incident_id
    assert alert.evidence_id == record.record_id
    api.operations.acknowledge(alert.alert_id, WRITER)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda _: api.operations.evaluate(WRITER), range(3)))
    assert len(api.incidents.list(READER)) == 1
    assert api.operations.list(READER)[0].acknowledged_by == WRITER.operator_id
    restart = ControlTowerAPI(
        api._registry,
        CapabilityDiscoveryService(),
        evidence_store=api.evidence,
        incident_service=IncidentService(api._registry, api.evidence, path),
    )
    assert restart.operations.list(READER)[0].incident_id == alert.incident_id
    assert restart.operations.list(READER)[0].first_seen == alert.first_seen
    assert api.get_agent("staging").status == "healthy"


@pytest.mark.parametrize("seconds", [-301, 60])
def test_stale_and_future_failures_never_create_incidents(tower, seconds):
    api, _ = tower
    evidence(api.evidence, observed_at=datetime.now(timezone.utc) + timedelta(seconds=seconds))
    alerts = api.operations.evaluate(WRITER)
    assert all(a.rule != "lens.failed" for a in alerts)
    assert api.incidents.list(READER) == []


def test_clearing_alert_does_not_resolve_recovery_incident(tower):
    api, _ = tower
    evidence(api.evidence)
    alert = api.operations.evaluate(WRITER)[0]
    evidence(api.evidence, status="succeeded", run_id="new-run")
    api.operations.evaluate(WRITER)
    assert api.operations.list(READER, active_only=True) == []
    assert api.operations.list(READER)[0].cleared_at
    assert api.incidents.get(alert.incident_id, READER).state == "open"


def test_missing_and_heartbeat_warnings_preserve_health(tower):
    api, _ = tower
    now = datetime.now(timezone.utc) + timedelta(seconds=301)
    alerts = api.operations.evaluate(WRITER, now=now)
    assert {a.rule for a in alerts} == {"heartbeat.stale", "evidence.missing"}
    assert api.get_status().healthy_agents == 1
    assert not api.operations.list(READER, environment="production")


def test_scope_and_role_apply_to_reads_acknowledgements_and_detection(tower):
    api, _ = tower
    evidence(api.evidence)
    alert = api.operations.evaluate(WRITER)[0]
    scoped = Operator(operator_id="other", role="writer", agent_ids=[])
    assert api.operations.list(scoped) == []
    with pytest.raises(IncidentError):
        api.operations.acknowledge(alert.alert_id, scoped)
    with pytest.raises(IncidentError):
        api.operations.acknowledge(alert.alert_id, READER)
    with pytest.raises(IncidentError):
        api.operations.evaluate(READER)
    assert api.operations.evaluate(scoped) == []
    with pytest.raises(IncidentError):
        api.operations.incident_view(alert.incident_id, scoped)


def test_view_joins_native_policy_and_change_audit_with_freshness(tower):
    api, _ = tower
    record = evidence(api.evidence)
    alert = api.operations.evaluate(WRITER)[0]
    api.config.declare(
        Configuration(agent_id="staging", capability="agenticlens", authority="tower"), WRITER
    )
    request = EvidenceIngestRequest.model_validate(
        dict(
            link=dict(
                agent_id="staging",
                source="agentic-sidecar",
                source_version="0.9.0",
                artifact_type="decision",
                artifact_ref="decision:1",
                run_id="failure",
                observed_at=datetime.now(timezone.utc).isoformat(),
            ),
            artifact=dict(decision_id="policy-1", status="BLOCK", risk="HIGH", reason="denied"),
        )
    )
    policy = api.ingest_evidence(request).record
    api.incidents.investigate(alert.incident_id, WRITER)
    view = api.operations.incident_view(alert.incident_id, READER)
    assert {r.record_id for r in view["evidence"]} == {record.record_id, policy.record_id}
    assert {e["source"] for e in view["timeline"]} >= {
        "incident",
        "configuration",
        "agentic-sidecar",
        "agenticlens",
    }
    assert view["lens_integrity"] == "not_verified"
    assert view["lens_coverage"] == "not_assessed"
    assert view["posture"].reported_health == "healthy"
    assert view["incident"].investigation


def test_http_alert_access_and_view(tower):
    api, _ = tower
    evidence(api.evidence)
    client = TestClient(create_app(api, read_token="r", write_token="w"))
    read, write = {"Authorization": "Bearer r"}, {"Authorization": "Bearer w"}
    assert client.get("/alerts").status_code == 401
    assert client.post("/alerts/evaluate", headers=read).status_code == 403
    alert = client.post("/alerts/evaluate", headers=write).json()[0]
    assert client.get("/alerts?active_only=true", headers=read).json()[0] == alert
    assert client.post(f"/alerts/{alert['alert_id']}/acknowledge", headers=read).status_code == 409
    result = client.post(f"/alerts/{alert['alert_id']}/acknowledge", headers=write)
    assert result.json()["acknowledged_by"] == "http-writer"
    assert client.get(f"/incidents/{alert['incident_id']}/view", headers=read).status_code == 200
    assert client.get("/incidents/unknown/view", headers=read).status_code == 409


def test_lifespan_polls_and_stops_cleanly(tower):
    import time

    api, _ = tower
    evidence(api.evidence)
    with TestClient(create_app(api, read_token="r", detection_interval_seconds=0.01)) as client:
        for _ in range(100):
            response = client.get("/alerts", headers={"Authorization": "Bearer r"})
            if response.json():
                break
            time.sleep(0.01)
        assert response.json()[0]["incident_id"]
    with pytest.raises(ValueError):
        create_app(api, detection_interval_seconds=-1)


def test_policy_bounds():
    with pytest.raises(ValueError):
        DetectionPolicy(stale_after_seconds=0)


def test_cli_live_alerts_and_joined_view(tower, capsys):
    import json

    from agenticops_control_tower.cli.main import main

    api, _ = tower
    evidence(api.evidence)
    client = TestClient(create_app(api, write_token="w"))
    assert main(["--token", "w", "alerts", "evaluate"], client=client) == 0
    alert = json.loads(capsys.readouterr().out)[0]
    assert main(["--token", "w", "alerts", "list", "--active-only"], client=client) == 0
    assert alert["alert_id"] in capsys.readouterr().out
    assert main(["--token", "w", "alerts", "acknowledge", alert["alert_id"]], client=client) == 0
    assert "http-writer" in capsys.readouterr().out
    assert main(["--token", "w", "incidents", "view", alert["incident_id"]], client=client) == 0
    assert "not_verified" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--snapshot", "unused.json", "alerts", "list"])


def test_out_of_order_scans_do_not_regress_alert_state_and_audit_is_append_only(tower):
    api, _ = tower
    record = evidence(api.evidence)
    now = datetime.now(timezone.utc)
    alert = api.operations.evaluate(WRITER, now=now)[0]
    api.operations.acknowledge(alert.alert_id, WRITER)
    api.operations.acknowledge(alert.alert_id, WRITER)
    api.operations.evaluate(WRITER, now=now + timedelta(seconds=301))
    api.operations.evaluate(WRITER, now=now)
    assert next(a for a in api.operations.list(READER) if a.alert_id == alert.alert_id).cleared_at
    view = api.operations.incident_view(alert.incident_id, READER)
    events = [e["event"] for e in view["timeline"] if e["source"] == "alert"]
    assert events.count("alert.acknowledged") == 1
    assert "alert.cleared" in events
    assert view["incident"].detection.record_id == record.record_id


def test_standalone_example():
    import runpy
    from pathlib import Path

    demo = runpy.run_path(str(Path(__file__).parents[1] / "examples/live_operations.py"))
    result = demo["walkthrough"]()
    assert result["alerts"] == 1
    assert result["state"] == "open"
    assert result["reported_health"] == "healthy"
    assert "alert.acknowledged" in result["events"]


def test_detection_does_not_hold_database_write_lock_during_telemetry_reads(tower, monkeypatch):
    api, path = tower
    evidence(api.evidence)
    history = api.evidence.history
    calls = 0

    def read_with_concurrent_push(*args, **kwargs):
        nonlocal calls
        calls += 1
        # A second SQLite writer must be able to commit while the scan reads.
        with ThreadPoolExecutor(1) as pool:
            pool.submit(
                evidence, EvidenceStore(api._registry, path), run_id=f"concurrent-{calls}"
            ).result(timeout=3)
        return history(*args, **kwargs)

    monkeypatch.setattr(api.evidence, "history", read_with_concurrent_push)
    api.operations.evaluate(WRITER)
    assert calls >= 2


def test_older_scan_cannot_create_orphan_incident_after_newer_stale_scan(tower):
    api, _ = tower
    evidence(api.evidence)
    now = datetime.now(timezone.utc)
    api.operations.evaluate(WRITER, now=now + timedelta(seconds=301))
    assert api.incidents.list(READER) == []
    api.operations.evaluate(WRITER, now=now)
    assert api.incidents.list(READER) == []
    assert all(a.rule != "lens.failed" for a in api.operations.list(READER))


def test_failed_scan_rolls_back_incident_and_alert_atomically(tower, monkeypatch):
    api, _ = tower
    evidence(api.evidence)

    def fail(*args):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(api.operations, "_save", fail)
    with pytest.raises(RuntimeError):
        api.operations.evaluate(WRITER)
    assert api.incidents.list(READER) == []
    assert api.operations.list(READER) == []


def test_incident_view_uses_native_detection_run_id(tower, monkeypatch):
    api, _ = tower
    ingest = api.evidence.ingest

    def without_link(request, **kwargs):
        request = request.model_copy(deep=True)
        request.link.run_id = None
        return ingest(request, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(api.evidence, "ingest", without_link)
        record = evidence(api.evidence)
    gate = evidence(api.evidence, "agentic-evals", "succeeded", "failure")
    alert = next(a for a in api.operations.evaluate(WRITER) if a.rule == "lens.failed")
    view = api.operations.incident_view(alert.incident_id, READER)
    assert {r.record_id for r in view["evidence"]} == {record.record_id, gate.record_id}


def test_incident_view_bounds_same_run_history_and_preserves_original_detection(tower):
    api, _ = tower
    record = evidence(api.evidence)
    alert = api.operations.evaluate(WRITER)[0]
    for index in range(105):
        api.ingest_evidence(
            EvidenceIngestRequest.model_validate(
                dict(
                    link=dict(
                        agent_id="staging",
                        source="agentic-sidecar",
                        source_version="0.9.0",
                        artifact_type="decision",
                        artifact_ref=f"decision:{index}",
                        run_id="failure",
                        observed_at=datetime.now(timezone.utc).isoformat(),
                    ),
                    artifact=dict(status="BLOCK", risk="HIGH", reason="denied"),
                )
            )
        )
    view = api.operations.incident_view(alert.incident_id, READER)
    assert view["evidence_truncated"] is True
    assert view["evidence_limit"] == 100
    assert len(view["evidence"]) == 101  # 100 recent records plus the retained original detection
    assert record.record_id in {r.record_id for r in view["evidence"]}
    with pytest.raises(ValueError):
        api.evidence.run_history("staging", "failure", limit=0)
