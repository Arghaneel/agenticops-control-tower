"""Posture rollups count native values, track freshness and never touch health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from agenticops_control_tower.evidence import EvidenceStore, PostureService, native_tallies
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.registry import AgentRegistry

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
TYPES = {
    "agenticlens": "run",
    "agentic-evals": "evaluation_report",
    "agentic-sidecar": "decision",
    "agentic-chaos": "chaos_report",
}


def setup() -> tuple[AgentRegistry, EvidenceStore, PostureService]:
    registry = AgentRegistry()
    for agent_id, environment in [("a", "staging"), ("b", "staging"), ("c", "production")]:
        registry.register(
            AgentRegistrationPayload(
                agent_id=agent_id,
                name=agent_id,
                environment=environment,
                runtime="python",
                framework="custom",
                status="unhealthy" if agent_id == "c" else "healthy",
            )
        )
    store = EvidenceStore(registry)
    return registry, store, PostureService(store)


def push(
    store: EvidenceStore,
    agent_id: str,
    source: str,
    ref: str,
    artifact: dict[str, Any] | None,
    *,
    age: timedelta = timedelta(minutes=1),
    gate: dict[str, Any] | None = None,
) -> None:
    store.ingest(
        EvidenceIngestRequest.model_validate(
            {
                "link": {
                    "agent_id": agent_id,
                    "source": source,
                    "source_version": "1.0.0",
                    "artifact_type": TYPES[source],
                    "artifact_ref": ref,
                    "observed_at": NOW - age,
                },
                "artifact": artifact,
                "gate": gate,
            }
        ),
        now=NOW,
    )


def run(status: str, *, failed_tool: str | None = None) -> dict[str, Any]:
    spans = []
    if failed_tool:
        spans.append(
            {
                "span_id": "s",
                "name": "call",
                "span_type": "tool_call",
                "tool_name": failed_tool,
                "status": "failed",
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": f"run-{status}",
        "application_name": "app",
        "status": status,
        "spans": spans,
    }


REPORT = {
    "schema_version": "1.0",
    "suite_name": "suite",
    "suite_version": "1",
    "created_at": "2026-10-13T11:00:00Z",
    "summary": {
        "total_cases": 2,
        "passed_cases": 1,
        "failed_cases": 1,
        "pass_rate": 0.5,
        "average_score": 0.5,
    },
}


def test_missing_sources_are_explicit_and_health_is_reported_not_derived() -> None:
    registry, _store, posture = setup()
    result = posture.agent(registry.get("c"), now=NOW)
    assert result.reported_health == "unhealthy"
    assert [s.source for s in result.sources] == list(TYPES)
    assert {s.freshness for s in result.sources} == {"missing"}
    assert all(s.reason == "No evidence recorded for this source" for s in result.sources)
    assert all(s.latest is None for s in result.sources)


def test_fresh_and_stale_freshness_use_observed_time() -> None:
    registry, store, posture = setup()
    push(store, "a", "agenticlens", "r1", run("succeeded"))
    push(store, "a", "agentic-chaos", "c1", None, age=timedelta(days=2))
    result = {s.source: s for s in posture.agent(registry.get("a"), now=NOW).sources}
    assert result["agenticlens"].freshness == "fresh"
    assert result["agenticlens"].reason is None
    assert result["agentic-chaos"].freshness == "stale"
    assert "older than 86400 seconds" in (result["agentic-chaos"].reason or "")
    assert result["agentic-chaos"].recent_records == 0
    short = posture.agent(registry.get("a"), now=NOW, stale_after_seconds=30)
    assert {s.source: s.freshness for s in short.sources}["agenticlens"] == "stale"


def test_native_tallies_count_producer_values_without_recomputing() -> None:
    registry, store, posture = setup()
    push(store, "a", "agenticlens", "r1", run("failed", failed_tool="payments_api"))
    push(store, "a", "agenticlens", "r2", run("succeeded"))
    push(store, "a", "agenticlens", "r3", {"broken": True})
    push(store, "a", "agentic-evals", "e1", REPORT)
    push(
        store,
        "a",
        "agentic-evals",
        "e2",
        REPORT,
        gate={"passed": False, "reasons": ["policy"], "observed": {}},
    )
    for ref, status, risk in [("d1", "BLOCK", "HIGH"), ("d2", "ESCALATE", None)]:
        push(
            store,
            "a",
            "agentic-sidecar",
            ref,
            {"status": status, "risk": risk, "reason": "producer", "escalation_required": True},
        )
    push(
        store,
        "a",
        "agentic-chaos",
        "c1",
        {
            "id": "x",
            "name": "outage",
            "start_time": "2026-10-13T11:00:00Z",
            "chaos_events": [{}, {}],
        },
    )
    result = {s.source: s for s in posture.agent(registry.get("a"), now=NOW).sources}
    lens = result["agenticlens"]
    assert lens.recent_records == 3
    assert lens.recent_unavailable == 1
    assert lens.summary == {
        "status_counts": {"running": 0, "succeeded": 1, "failed": 1},
        "failed_tool_names": ["payments_api"],
    }
    assert result["agentic-evals"].summary["gate_counts"] == {
        "passed": 0,
        "failed": 1,
        "not_supplied": 1,
    }
    sidecar = result["agentic-sidecar"].summary
    assert sidecar["status_counts"]["BLOCK"] == 1
    assert sidecar["status_counts"]["ESCALATE"] == 1
    assert sidecar["risk_counts"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 1, "unclassified": 1}
    assert sidecar["escalations_required"] == 2
    assert result["agentic-chaos"].summary == {
        "experiments": 1,
        "completed": 0,
        "incomplete": 1,
        "fault_events": 2,
    }
    assert registry.get("a").status == "healthy"


def test_latest_unavailable_reason_is_surfaced() -> None:
    registry, store, posture = setup()
    push(store, "a", "agentic-sidecar", "d1", {"status": "nope"})
    result = {s.source: s for s in posture.agent(registry.get("a"), now=NOW).sources}
    sidecar = result["agentic-sidecar"]
    assert sidecar.freshness == "fresh"
    assert sidecar.latest is not None
    assert sidecar.latest.summary.availability == "unavailable"
    assert "status" in (sidecar.reason or "")


def test_fleet_posture_groups_agents_and_merges_tallies() -> None:
    registry, store, posture = setup()
    push(store, "a", "agenticlens", "r1", run("failed", failed_tool="db"))
    push(store, "b", "agenticlens", "r2", run("failed", failed_tool="cache"))
    push(store, "b", "agentic-sidecar", "d1", None)
    push(store, "c", "agenticlens", "r3", run("succeeded"), age=timedelta(days=3))
    fleet = posture.fleet(registry.list_agents(), now=NOW)
    sources = {s.source: s for s in fleet.sources}
    assert fleet.total_agents == 3
    lens = sources["agenticlens"]
    assert lens.fresh_agents == ["a", "b"]
    assert lens.stale_agents == ["c"]
    assert lens.missing_agents == []
    assert lens.summary["status_counts"]["failed"] == 2
    assert lens.summary["failed_tool_names"] == ["cache", "db"]
    assert sources["agentic-sidecar"].latest_unavailable_agents == ["b"]
    assert sources["agentic-sidecar"].missing_agents == ["a", "c"]
    assert sources["agentic-chaos"].summary == native_tallies("agentic-chaos", [])
    staging = posture.fleet(
        [a for a in registry.list_agents() if a.environment == "staging"],
        environment="staging",
        now=NOW,
    )
    assert staging.environment == "staging"
    assert staging.total_agents == 2
