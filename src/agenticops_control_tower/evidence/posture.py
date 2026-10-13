"""Read-only evidence posture over persisted projections.

Tallies count native producer values (run status, gate passed, decision
status and risk, chaos completion). They never recompute an evaluation,
supervision decision or resilience verdict, and never change fleet health.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from agenticops_control_tower.models import AgentRecord
from agenticops_control_tower.models.evidence import (
    EVIDENCE_SOURCES,
    AgentEvidencePosture,
    EvidenceRecord,
    EvidenceSource,
    FleetEvidencePosture,
    FleetSourcePosture,
    SourcePosture,
)

from .store import EvidenceStore, as_utc

DEFAULT_STALE_AFTER_SECONDS = 24 * 60 * 60

_LENS_STATUSES = ("running", "succeeded", "failed")
_SIDECAR_STATUSES = ("ALLOW", "WARN", "BLOCK", "CHALLENGE", "REPLAN", "PAUSE", "ESCALATE")
_SIDECAR_RISKS = ("LOW", "MEDIUM", "HIGH")


def _count(values: Iterable[str], keys: Iterable[str]) -> dict[str, int]:
    counts = dict.fromkeys(keys, 0)
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def native_tallies(source: EvidenceSource, records: list[EvidenceRecord]) -> dict[str, Any]:
    """Count native outcomes in available projections for one source."""
    details = [r.summary.details for r in records if r.summary.availability == "available"]
    if source == "agenticlens":
        return {
            "status_counts": _count((d["status"] for d in details), _LENS_STATUSES),
            "failed_tool_names": sorted(
                {
                    span["tool_name"]
                    for d in details
                    for span in d.get("failed_spans", [])
                    if span.get("tool_name")
                }
            ),
        }
    if source == "agentic-evals":
        return {
            "gate_counts": _count(
                (
                    "not_supplied"
                    if d.get("gate") is None
                    else ("passed" if d["gate"]["passed"] else "failed")
                    for d in details
                ),
                ("passed", "failed", "not_supplied"),
            )
        }
    if source == "agentic-sidecar":
        return {
            "status_counts": _count((d["status"] for d in details), _SIDECAR_STATUSES),
            "risk_counts": _count(
                (d["risk"] or "unclassified" for d in details), (*_SIDECAR_RISKS, "unclassified")
            ),
            "escalations_required": sum(1 for d in details if d.get("escalation_required")),
        }
    return {
        "experiments": len(details),
        "completed": sum(1 for d in details if d["completed"]),
        "incomplete": sum(1 for d in details if not d["completed"]),
        "fault_events": sum(int(d["event_count"]) for d in details),
    }


def _merge(total: dict[str, Any], part: dict[str, Any]) -> dict[str, Any]:
    for key, value in part.items():
        if isinstance(value, dict):
            total[key] = _merge(dict(total.get(key, {})), value)
        elif isinstance(value, list):
            total[key] = sorted(set(total.get(key, [])) | set(value))
        else:
            total[key] = total.get(key, 0) + value
    return total


class PostureService:
    def __init__(self, store: EvidenceStore) -> None:
        self.store = store

    def source(
        self,
        agent_id: str,
        source: EvidenceSource,
        *,
        now: datetime,
        stale_after_seconds: int,
    ) -> SourcePosture:
        latest = next(iter(self.store.history(agent_id, source=source, limit=1)), None)
        cutoff = now - timedelta(seconds=stale_after_seconds)
        recent = self.store.history(agent_id, source=source, since=cutoff, limit=None)
        posture = SourcePosture(
            source=source,
            freshness="missing",
            reason="No evidence recorded for this source",
            latest=latest,
            recent_records=len(recent),
            recent_unavailable=sum(1 for r in recent if r.summary.availability == "unavailable"),
            summary=native_tallies(source, recent),
        )
        if latest is None:
            return posture
        if as_utc(latest.summary.link.observed_at) >= cutoff:
            posture.freshness = "fresh"
            posture.reason = latest.summary.reason
        else:
            posture.freshness = "stale"
            posture.reason = f"Latest evidence is older than {stale_after_seconds} seconds"
        return posture

    def agent(
        self,
        agent: AgentRecord,
        *,
        now: datetime | None = None,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    ) -> AgentEvidencePosture:
        now = now or datetime.now(timezone.utc)
        return AgentEvidencePosture(
            agent_id=agent.agent_id,
            environment=agent.environment,
            reported_health=agent.status,
            evaluated_at=now,
            stale_after_seconds=stale_after_seconds,
            sources=[
                self.source(
                    agent.agent_id, source, now=now, stale_after_seconds=stale_after_seconds
                )
                for source in EVIDENCE_SOURCES
            ],
        )

    def fleet(
        self,
        agents: list[AgentRecord],
        *,
        environment: str | None = None,
        now: datetime | None = None,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    ) -> FleetEvidencePosture:
        now = now or datetime.now(timezone.utc)
        fleet = {source: FleetSourcePosture(source=source) for source in EVIDENCE_SOURCES}
        for agent in agents:
            posture = self.agent(agent, now=now, stale_after_seconds=stale_after_seconds)
            for item in posture.sources:
                target = fleet[item.source]
                getattr(target, f"{item.freshness}_agents").append(agent.agent_id)
                if item.latest is not None and item.latest.summary.availability == "unavailable":
                    target.latest_unavailable_agents.append(agent.agent_id)
                target.summary = _merge(target.summary, item.summary)
        for source in EVIDENCE_SOURCES:
            if not fleet[source].summary:
                fleet[source].summary = native_tallies(source, [])
        return FleetEvidencePosture(
            evaluated_at=now,
            environment=environment,
            stale_after_seconds=stale_after_seconds,
            total_agents=len(agents),
            sources=list(fleet.values()),
        )
