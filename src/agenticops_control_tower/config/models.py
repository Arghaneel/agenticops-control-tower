"""Configuration ownership and reusable bounded action contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue

from agenticops_control_tower.models.agent import AgentId


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigScope(Contract):
    agent_id: AgentId
    environment: str | None = None
    capability: str | None = None


class ConfigPatch(Contract):
    values: dict[str, JsonValue] = Field(default_factory=dict)


class Operator(Contract):
    """Trusted caller identity; HTTP derives it from server-side credentials."""

    operator_id: str = Field(min_length=1)
    role: Literal["reader", "writer", "approver"]
    agent_ids: list[str] | None = None


class Configuration(Contract):
    agent_id: AgentId
    capability: str = Field(min_length=1)
    authority: Literal["tower", "mirrored", "unsupported"] = "unsupported"
    values: dict[str, JsonValue] = Field(default_factory=dict)
    enabled: bool | None = None
    revision: int = Field(default=0, ge=0)
    reason: str = "No writable runtime adapter is installed"


class ActionRequest(Contract):
    target: ConfigScope
    operation: Literal["config.update", "capabilities.enable", "capabilities.disable"]
    patch: ConfigPatch = Field(default_factory=ConfigPatch)
    expires_in_seconds: int = Field(default=300, ge=1, le=3600)


class ActionPreview(Contract):
    action_id: str
    request: ActionRequest
    proposed_by: str
    expected_revision: int
    before: Configuration
    after: Configuration
    impact: str
    expires_at: AwareDatetime
    status: Literal["pending", "approved", "denied", "executed", "revoked"] = "pending"
    approved_by: str | None = None


class ApprovalRequest(Contract):
    approved: bool


class ExecutionResult(Contract):
    action_id: str
    outcome: Literal["succeeded", "failed", "partial_failure"]
    configuration: Configuration
    rollback: Literal["not_needed", "succeeded", "failed"] = "not_needed"
    reconciliation: str = (
        "Tower desired configuration committed; runtime application is not asserted"
    )


class AuditRecord(Contract):
    event_id: str
    action_id: str | None = None
    operator_id: str
    event: str
    agent_id: str
    recorded_at: AwareDatetime
    detail: str = ""
