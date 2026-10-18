"""Tower-local fleet operation contracts; no shared AIOS schema is implied."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from agenticops_control_tower.config.models import ActionPreview, ConfigPatch, Contract
from agenticops_control_tower.models.agent import AgentId


class FleetSelector(Contract):
    environment: str = Field(min_length=1)
    capability: AgentId
    agent_ids: list[AgentId] | None = Field(default=None, min_length=1, max_length=100)


class BulkRequest(Contract):
    intent: str = Field(min_length=1, max_length=1000)
    selector: FleetSelector
    operation: Literal[
        "config.update", "capabilities.enable", "capabilities.disable", "runtime.stop"
    ]
    patch: ConfigPatch = Field(default_factory=ConfigPatch)
    expires_in_seconds: int = Field(default=300, ge=1, le=3600)
    acknowledgement_seconds: float = Field(default=5, ge=0.01, le=30, allow_inf_nan=False)

    execution_seconds: float = Field(default=30, ge=0.01, le=30, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_patch(self) -> "BulkRequest":
        if self.operation != "config.update" and self.patch.values:
            raise ValueError("Only config.update accepts a patch")
        return self


class TargetResult(Contract):
    agent_id: str
    command_id: str
    deployment: dict[str, str] = Field(default_factory=dict)
    preview: ActionPreview | None = None
    outcome: Literal[
        "pending",
        "requested",
        "succeeded",
        "acknowledged",
        "failed",
        "unsupported",
        "incomplete",
        "timed_out",
        "unknown",
    ] = "pending"
    detail: str = ""
    receipt: dict[str, object] = Field(default_factory=dict)


class BulkEvent(Contract):
    event: str
    operator_id: str
    recorded_at: AwareDatetime
    agent_id: str | None = None


class BulkAction(Contract):
    bulk_id: str
    request: BulkRequest
    proposed_by: str
    expires_at: AwareDatetime
    status: Literal["pending", "approved", "denied", "revoked", "executing", "completed"] = (
        "pending"
    )
    decided_by: str | None = None
    targets: list[TargetResult]
    events: list[BulkEvent] = Field(default_factory=list)
    reconciliation: str = (
        "No fleet atomicity or automatic rollback. Inspect per-target results; preview a new "
        "operation for failed/unattempted targets. Requested or timed-out runtime commands "
        "require host reconciliation before any retry. Stop blocks dispatch and requests "
        "MCP revocation only; in-flight calls and downstream credentials remain explicit limits."
    )
