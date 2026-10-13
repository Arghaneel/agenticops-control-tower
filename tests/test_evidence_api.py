"""Python facade for evidence ingestion, history and posture."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agenticops_control_tower.errors import AgentNotFoundError
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.snapshot import create_api

OBSERVED = datetime.now(timezone.utc) - timedelta(seconds=5)


def request(agent_id: str = "payments", status: str = "PAUSE") -> EvidenceIngestRequest:
    return EvidenceIngestRequest.model_validate(
        {
            "link": {
                "agent_id": agent_id,
                "source": "agentic-sidecar",
                "source_version": "0.7.0",
                "artifact_type": "decision",
                "artifact_ref": f"decision:{status}",
                "observed_at": OBSERVED,
            },
            "artifact": {"status": status, "risk": "HIGH", "reason": "producer"},
        }
    )


def api_with_agent():
    api = create_api()
    api.register(
        AgentRegistrationPayload(
            agent_id="payments",
            name="Payments",
            environment="staging",
            runtime="python",
            framework="custom",
            status="healthy",
        )
    )
    return api


def test_ingest_history_and_posture_share_one_store() -> None:
    api = api_with_agent()
    assert api.ingest_evidence(request(), ingested_by="ops").created
    assert api.ingest_evidence(request()).created is False
    history = api.evidence_history("payments", source="agentic-sidecar")
    assert [r.summary.details["status"] for r in history] == ["PAUSE"]
    assert history[0].ingested_by == "ops"
    posture = {s.source: s for s in api.agent_posture("payments").sources}
    assert posture["agentic-sidecar"].freshness == "fresh"
    assert posture["agenticlens"].freshness == "missing"
    fleet = api.fleet_posture(environment="staging")
    assert fleet.total_agents == 1
    assert api.fleet_posture(environment="production").total_agents == 0
    assert api.get_status().healthy_agents == 1


def test_summarize_evidence_still_does_not_persist() -> None:
    api = api_with_agent()
    api.summarize_evidence(request().link, request().artifact)
    assert api.evidence_history("payments") == []


def test_unknown_deployments_raise() -> None:
    api = api_with_agent()
    with pytest.raises(AgentNotFoundError):
        api.ingest_evidence(request("absent"))
    with pytest.raises(AgentNotFoundError):
        api.agent_posture("absent")
