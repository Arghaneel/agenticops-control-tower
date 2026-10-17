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
        acknowledged = (
            action == "stop"
            and receipt.get("action") == "stop"
            and revocations.get("mcp") is True
            and receipt.get("access_revocation") == "acknowledged"
        )
        return {
            "action": action,
            "dispatch_blocking": "acknowledged" if action == "stop" else "restart_acknowledged",
            "mcp_revocation": "acknowledged"
            if revocations.get("mcp") is True
            else "unsupported_or_failed",
            "in_flight": running,
            "downstream_credentials": "unsupported",
            "containment": "boundary_acknowledged"
            if acknowledged and not running
            else "incomplete",
        }
