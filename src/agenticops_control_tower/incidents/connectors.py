"""Explicit bounded connector boundary. No command strings or caller-provided URLs."""

from typing import Literal, Protocol

from agenticops_control_tower.incidents.models import RecoveryPlan


class RecoveryConnector(Protocol):
    """Installed by the trusted host; enforce timeout and idempotency at the runtime.

    A connector must return within timeout_seconds, never retry an unsafe action,
    and use incident_id as its durable idempotency key. A crash leaves execution
    unknown and requires manual reconciliation, never automatic replay.
    """

    def supports(self, agent_id: str, dependency: str) -> bool: ...

    def execute(
        self, incident_id: str, plan: RecoveryPlan
    ) -> Literal["succeeded", "failed", "partial_failure"]: ...

    def probe(self, plan: RecoveryPlan) -> bool: ...
