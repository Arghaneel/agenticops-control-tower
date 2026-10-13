"""Durable, idempotent evidence history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agenticops_control_tower.errors import AgentNotFoundError
from agenticops_control_tower.evidence import EvidenceIngestError, EvidenceStore
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.registry import AgentRegistry

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def registry(path: str | None = None) -> AgentRegistry:
    result = AgentRegistry(path)
    result.register(
        AgentRegistrationPayload(
            agent_id="payments",
            name="Payments",
            environment="staging",
            runtime="python",
            framework="custom",
            status="healthy",
        )
    )
    return result


def decision(ref: str, observed_at: datetime, status: str = "BLOCK") -> EvidenceIngestRequest:
    return EvidenceIngestRequest.model_validate(
        {
            "link": {
                "agent_id": "payments",
                "source": "agentic-sidecar",
                "source_version": "0.7.0",
                "artifact_type": "decision",
                "artifact_ref": ref,
                "observed_at": observed_at,
            },
            "artifact": {"status": status, "risk": "HIGH", "reason": "producer policy"},
        }
    )


def test_ingest_is_idempotent_for_the_same_attributed_observation() -> None:
    store = EvidenceStore(registry())
    first = store.ingest(decision("d1", NOW), ingested_by="writer", now=NOW)
    retry = store.ingest(decision("d1", NOW, status="ALLOW"), now=NOW + timedelta(seconds=1))
    assert first.created is True
    assert retry.created is False
    assert retry.record == first.record
    assert retry.record.summary.details["status"] == "BLOCK"
    assert first.record.ingested_by == "writer"
    assert len(store.history("payments")) == 1


def test_naive_and_aware_timestamps_share_identity() -> None:
    store = EvidenceStore(registry())
    store.ingest(decision("d1", NOW), now=NOW)
    assert store.ingest(decision("d1", NOW.replace(tzinfo=None)), now=NOW).created is False


def test_unavailable_projections_are_recorded_with_reason() -> None:
    store = EvidenceStore(registry())
    request = decision("bad", NOW)
    request.artifact = {"status": "MAYBE"}
    record = store.ingest(request, now=NOW).record
    assert record.summary.availability == "unavailable"
    assert "status" in (record.summary.reason or "")
    assert store.history("payments")[0].record_id == record.record_id


def test_history_orders_filters_and_limits() -> None:
    store = EvidenceStore(registry())
    for minutes, ref in [(3, "old"), (1, "new"), (2, "middle")]:
        store.ingest(decision(ref, NOW - timedelta(minutes=minutes)), now=NOW)
    refs = [r.summary.link.artifact_ref for r in store.history("payments")]
    assert refs == ["new", "middle", "old"]
    assert len(store.history("payments", limit=1)) == 1
    assert store.history("payments", source="agenticlens") == []
    since = [
        r.summary.link.artifact_ref
        for r in store.history("payments", since=NOW - timedelta(minutes=2))
    ]
    assert since == ["new", "middle"]


def test_unknown_deployments_and_future_observations_are_rejected() -> None:
    store = EvidenceStore(registry())
    request = decision("d1", NOW)
    request.link.agent_id = "absent"
    with pytest.raises(AgentNotFoundError):
        store.ingest(request, now=NOW)
    with pytest.raises(AgentNotFoundError):
        store.history("absent")
    with pytest.raises(EvidenceIngestError):
        store.ingest(decision("future", NOW + timedelta(minutes=6)), now=NOW)
    assert store.ingest(decision("skew", NOW + timedelta(minutes=4)), now=NOW).created


def test_sqlite_history_survives_restart_and_prunes(tmp_path: Path) -> None:
    path = str(tmp_path / "tower.sqlite")
    EvidenceStore(registry(path), path).ingest(decision("d1", NOW - timedelta(days=2)), now=NOW)
    EvidenceStore(registry(path), path).ingest(decision("d2", NOW), now=NOW)
    restarted = EvidenceStore(AgentRegistry(path), path)
    assert [r.summary.link.artifact_ref for r in restarted.history("payments")] == ["d2", "d1"]
    assert restarted.prune(NOW - timedelta(days=1)) == 1
    assert [r.summary.link.artifact_ref for r in restarted.history("payments")] == ["d2"]
    with sqlite3.connect(path) as db:
        bodies = [row[0] for row in db.execute("SELECT body FROM tower_evidence")]
    assert "producer policy" in bodies[0]
