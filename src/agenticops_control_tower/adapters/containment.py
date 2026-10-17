"""Thin Sidecar/MCP emergency braking adapters; credentials stay host-owned."""

from typing import Any, Protocol


class KeyIssuer(Protocol):
    def revoke(self, user: str, token: str) -> None: ...
    def authenticate(self, token: str) -> str | None: ...


class MCPAccessRevoker:
    """Bind one task to its hosted MCP issuer credential, never to caller input."""

    def __init__(self, issuer: KeyIssuer, task_id: str, user: str, token: str) -> None:
        self._issuer, self._task_id, self._user, self._token = issuer, task_id, user, token

    def __call__(self, task_id: str) -> bool:
        if task_id != self._task_id:
            return False
        if self._issuer.authenticate(self._token) is None:
            return True
        self._issuer.revoke(self._user, self._token)
        return self._issuer.authenticate(self._token) is None


class SidecarRuntime(Protocol):
    def control(self, action: str, actor: str) -> dict[str, Any]: ...


class SidecarContainmentAdapter:
    """Sidecar owns dispatch blocking; its installed revokers own access revocation.

    Requires a TaskRuntime configured with an `mcp` revoker. In-flight calls and
    downstream credentials remain explicitly outside complete containment.
    """

    def __init__(self, runtime: SidecarRuntime) -> None:
        self._runtime = runtime

    def control(self, action: str, actor: str) -> dict[str, Any]:
        receipt = self._runtime.control(action, actor)
        running = receipt.get("running", [])
        revocations = receipt.get("revocations", {})
        matches = receipt.get("action") == action
        outcome = "failed"
        if matches and action == "restart":
            outcome = "acknowledged"
        elif matches and action == "stop":
            if "mcp" not in revocations:
                outcome = "unsupported"
            elif (
                revocations["mcp"] is not True or receipt.get("access_revocation") != "acknowledged"
            ):
                outcome = "failed"
            elif running:
                outcome = "incomplete"
            else:
                outcome = "acknowledged"
        return {
            "action": action,
            "outcome": outcome,
            "dispatch_blocking": "acknowledged" if matches and action == "stop" else "not_asserted",
            "restart_acknowledgement": "acknowledged"
            if matches and action == "restart"
            else "failed"
            if action == "restart"
            else "not_requested",
            "mcp_revocation": "acknowledged"
            if revocations.get("mcp") is True
            else "failed"
            if "mcp" in revocations
            else "unsupported",
            "in_flight": running,
            "downstream_credentials": "unsupported",
            "containment": "boundary_acknowledged"
            if action == "stop" and outcome == "acknowledged"
            else "incomplete"
            if action == "stop"
            else "not_asserted",
        }
