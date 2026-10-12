"""Optional authenticated HTTP surface over the shared control model."""

from __future__ import annotations

import os
from secrets import compare_digest

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from agenticops_control_tower import __version__
from agenticops_control_tower.api.surface import ControlTowerAPI
from agenticops_control_tower.config.models import ActionRequest, ApprovalRequest, Operator
from agenticops_control_tower.config.service import ConfigurationError, ConfigurationService
from agenticops_control_tower.console.app import ASSET_DIRECTORY
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.errors import AgentNotFoundError
from agenticops_control_tower.models import (
    AgentRecord,
    AgentRegistrationPayload,
    AgentStatus,
    FleetStatusSummary,
    HeartbeatPayload,
)
from agenticops_control_tower.models.version import VersionAssessment
from agenticops_control_tower.registry import AgentRegistry


def create_app(
    api: ControlTowerAPI | None = None,
    *,
    database_path: str | None = None,
    read_token: str | None = None,
    write_token: str | None = None,
    approval_token: str | None = None,
) -> FastAPI:
    """Configure SQLite and reader/writer bearer tokens via arguments or environment.

    With no tokens configured, local development access is anonymous.
    Reader-only configuration rejects writes. Writer tokens also permit reads.
    """
    database_path = database_path or os.environ.get("AGENTICOPS_DATABASE")
    read_token = read_token or os.environ.get("AGENTICOPS_READ_TOKEN")
    write_token = write_token or os.environ.get("AGENTICOPS_WRITE_TOKEN")
    approval_token = approval_token or os.environ.get("AGENTICOPS_APPROVAL_TOKEN")
    if approval_token and approval_token in (read_token, write_token):
        raise ValueError("Approval token must differ from reader and writer tokens")
    if api is None:
        registry = AgentRegistry(database_path)
        api = ControlTowerAPI(
            registry,
            CapabilityDiscoveryService(),
            configuration_service=ConfigurationService(registry, database_path),
        )
    control_api = api
    app = FastAPI(title="AgenticOps Control Tower", version=__version__)
    bearer = HTTPBearer(auto_error=False)

    def authorize(credentials: HTTPAuthorizationCredentials | None, *, write: bool) -> None:
        if not read_token and not write_token and not approval_token:
            return
        if credentials is None:
            raise HTTPException(
                401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"}
            )
        token = credentials.credentials
        is_writer = bool(write_token and compare_digest(token.encode(), write_token.encode()))
        is_reader = bool(read_token and compare_digest(token.encode(), read_token.encode()))
        is_approver = bool(
            approval_token and compare_digest(token.encode(), approval_token.encode())
        )
        if not is_writer and not is_reader and not is_approver:
            raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})
        if write and not is_writer:
            raise HTTPException(403, "Writer token required")

    def read_access(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
        authorize(credentials, write=False)

    def write_access(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
        authorize(credentials, write=True)

    @app.post(
        "/agents/register",
        response_model=AgentRecord,
        status_code=201,
        dependencies=[Depends(write_access)],
    )
    def register_agent(agent: AgentRegistrationPayload) -> AgentRecord:
        return control_api.register(agent)

    @app.post(
        "/agents/{agent_id}/heartbeat",
        response_model=AgentRecord,
        dependencies=[Depends(write_access)],
    )
    def send_heartbeat(agent_id: str, payload: HeartbeatPayload) -> AgentRecord:
        try:
            return control_api.heartbeat(agent_id, payload)
        except AgentNotFoundError as exc:
            raise HTTPException(404, f"unknown agent: {agent_id}") from exc

    @app.get("/agents", response_model=list[AgentRecord], dependencies=[Depends(read_access)])
    def list_agents(
        status: AgentStatus | None = None,
        environment: str | None = None,
        capability: str | None = None,
        missing_capability: str | None = None,
    ) -> list[AgentRecord]:
        return control_api.list_agents(
            status=status,
            environment=environment,
            capability=capability,
            missing_capability=missing_capability,
        )

    @app.get("/agents/{agent_id}", response_model=AgentRecord, dependencies=[Depends(read_access)])
    def get_agent(agent_id: str) -> AgentRecord:
        try:
            return control_api.get_agent(agent_id)
        except AgentNotFoundError as exc:
            raise HTTPException(404, f"unknown agent: {agent_id}") from exc

    @app.get("/capabilities", dependencies=[Depends(read_access)])
    def list_capabilities() -> dict[str, list[str]]:
        return control_api.list_all_capabilities()

    @app.get("/status", response_model=FleetStatusSummary, dependencies=[Depends(read_access)])
    def get_status(environment: str | None = None) -> FleetStatusSummary:
        return control_api.get_status(environment=environment)

    @app.get(
        "/versions", response_model=list[VersionAssessment], dependencies=[Depends(read_access)]
    )
    def versions(
        capability: str = Query(min_length=1),
        minimum_version: str = Query(min_length=1),
        environment: str | None = None,
    ) -> list[VersionAssessment]:
        try:
            return control_api.assess_versions(capability, minimum_version, environment=environment)
        except ValueError as exc:
            raise HTTPException(422, "Minimum version must be a valid PEP 440 version") from exc

    @app.get("/agents/{agent_id}/evidence", dependencies=[Depends(read_access)])
    def evidence_readiness(agent_id: str) -> dict[str, str]:
        try:
            control_api.get_agent(agent_id)
        except AgentNotFoundError as exc:
            raise HTTPException(404, f"unknown agent: {agent_id}") from exc
        return {
            "agent_id": agent_id,
            "availability": "unavailable",
            "reason": "Evidence is not collected or persisted by this service. "
            "Native artifact readers are available through the Python API.",
        }

    def configuration_operator(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> Operator:
        authorize(credentials, write=False)
        if credentials is None:
            raise HTTPException(403, "Configuration actions require configured bearer credentials")
        token = credentials.credentials.encode()
        if write_token and compare_digest(token, write_token.encode()):
            return Operator(operator_id="http-writer", role="writer")
        if approval_token and compare_digest(token, approval_token.encode()):
            return Operator(operator_id="http-approver", role="approver")
        return Operator(operator_id="http-reader", role="reader")

    @app.get("/agents/{agent_id}/config/{capability}", dependencies=[Depends(read_access)])
    def configuration(agent_id: str, capability: str) -> object:
        try:
            return control_api.config.get(agent_id, capability)
        except AgentNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/agents/{agent_id}/audit", dependencies=[Depends(read_access)])
    def configuration_audit(agent_id: str) -> object:
        try:
            return control_api.config.audit(agent_id)
        except AgentNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/actions/preview")
    def preview_action(
        request: ActionRequest,
        operator: Operator = Depends(configuration_operator),
    ) -> object:
        try:
            return control_api.config.preview(request, operator)
        except AgentNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ConfigurationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/actions/{action_id}", dependencies=[Depends(read_access)])
    def get_action(action_id: str) -> object:
        try:
            return control_api.config.action(action_id)
        except ConfigurationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/actions/{action_id}/approval")
    def approve_action(
        action_id: str,
        request: ApprovalRequest,
        operator: Operator = Depends(configuration_operator),
    ) -> object:
        try:
            return control_api.config.approve(action_id, request.approved, operator)
        except ConfigurationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/actions/{action_id}/revoke")
    def revoke_action(
        action_id: str,
        operator: Operator = Depends(configuration_operator),
    ) -> object:
        try:
            return control_api.config.revoke(action_id, operator)
        except ConfigurationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/actions/{action_id}/execute")
    def execute_action(
        action_id: str,
        operator: Operator = Depends(configuration_operator),
    ) -> object:
        try:
            return control_api.config.execute(action_id, operator)
        except AgentNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ConfigurationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/console", include_in_schema=False)
    def console_redirect() -> RedirectResponse:
        return RedirectResponse("./console/")

    @app.get("/console/", include_in_schema=False)
    def console() -> FileResponse:
        # The public shell contains no inventory. Data reads use bearer authorization.
        return FileResponse(
            ASSET_DIRECTORY / "index.html",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; "
                "style-src 'self'; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    app.mount("/console/assets", StaticFiles(directory=ASSET_DIRECTORY), name="console-assets")
    return app
