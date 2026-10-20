"""Operator alert contracts, independent of native producer verdicts."""

from typing import Literal

from pydantic import AwareDatetime, Field

from agenticops_control_tower.config.models import Contract


class DetectionPolicy(Contract):
    stale_after_seconds: int = Field(default=300, ge=1, le=86400)
    heartbeat_after_seconds: int = Field(default=300, ge=1, le=86400)


class Alert(Contract):
    alert_id: str
    agent_id: str
    environment: str
    rule: Literal["lens.failed", "heartbeat.stale", "evidence.stale", "evidence.missing"]
    source: str
    severity: Literal["warning", "critical"]
    message: str
    correlation_key: str
    evidence_id: str | None = None
    incident_id: str | None = None
    first_seen: AwareDatetime
    last_seen: AwareDatetime
    cleared_at: AwareDatetime | None = None
    acknowledged_by: str | None = None
    acknowledged_at: AwareDatetime | None = None
