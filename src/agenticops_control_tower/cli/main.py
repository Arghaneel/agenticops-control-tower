"""Operator CLI (v0.2), talking to the v0.1 HTTP API.

The CLI connects to a running HTTP server, or inspects an offline fleet snapshot.
`serve --database` enables durable SQLite storage; bearer tokens are configured
through environment variables and supplied by `--token` or AGENTICOPS_TOKEN.

Requires the `api` extra for `httpx` (`pip install agenticops-control-tower[api]`).
The import itself stays cheap -- `httpx` is only imported inside the
functions that need it, so `from agenticops_control_tower.cli.main import
main` works even without the extra installed; only actually running a
command that talks to the API requires it.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

DEFAULT_API_URL = "http://localhost:8000"


def _client(api_url: str, client: httpx.Client | None = None) -> httpx.Client:
    if client is not None:
        return client
    try:
        import httpx
    except ImportError as exc:
        raise SystemExit(
            "This command talks to the Control Tower HTTP API and needs `httpx`. "
            "Install it with: pip install agenticops-control-tower[api]"
        ) from exc
    return httpx.Client(base_url=api_url)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_error:
        detail = response.text
        with contextlib.suppress(ValueError):
            detail = response.json().get("detail", detail)
        raise SystemExit(f"Control Tower API returned {response.status_code}: {detail}")


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        raise SystemExit(
            "`serve` needs uvicorn. Install it with: pip install agenticops-control-tower[api]"
        ) from None
    from agenticops_control_tower.api.http import create_app

    uvicorn.run(
        create_app(database_path=args.database),
        host=args.host,
        port=args.port,
    )
    return 0


def _load_payload(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _cmd_agents_register(args: argparse.Namespace, client: httpx.Client) -> int:
    payload = _load_payload(args.payload_file)
    response = client.post("/agents/register", json=payload)
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _cmd_agents_heartbeat(args: argparse.Namespace, client: httpx.Client) -> int:
    payload = _load_payload(args.payload_file)
    response = client.post(f"/agents/{args.agent_id}/heartbeat", json=payload)
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _cmd_agents_list(args: argparse.Namespace, client: httpx.Client) -> int:
    response = client.get(
        "/agents",
        params={
            key: getattr(args, key)
            for key in ("status", "environment", "capability", "missing_capability")
            if getattr(args, key) is not None
        },
    )
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _cmd_agents_get(args: argparse.Namespace, client: httpx.Client) -> int:
    response = client.get(f"/agents/{args.agent_id}")
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _cmd_capabilities_list(_args: argparse.Namespace, client: httpx.Client) -> int:
    response = client.get("/capabilities")
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _cmd_status(args: argparse.Namespace, client: httpx.Client) -> int:
    response = client.get(
        "/status", params={"environment": args.environment} if args.environment else {}
    )
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _cmd_configuration(args: argparse.Namespace, client: httpx.Client) -> int:
    if args.command == "config":
        response = client.get(f"/agents/{args.agent_id}/config/{args.capability}")
    elif args.command == "audit":
        response = client.get(f"/agents/{args.agent_id}/audit")
    elif args.action_command == "preview":
        response = client.post("/actions/preview", json=_load_payload(args.payload_file))
    elif args.action_command == "get":
        response = client.get(f"/actions/{args.action_id}")
    elif args.action_command in ("approve", "deny"):
        response = client.post(
            f"/actions/{args.action_id}/approval",
            json={"approved": args.action_command == "approve"},
        )
    else:
        response = client.post(f"/actions/{args.action_id}/{args.action_command}")
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _post_evidence(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/evidence", json=body)
    _raise_for_status(response)
    result: dict[str, Any] = response.json()
    return result


def _link(args: argparse.Namespace, source: str, artifact_ref: str, observed_at: str) -> Any:
    from agenticops_control_tower.adapters.evidence import ARTIFACT_TYPES

    link = {
        "agent_id": args.agent_id,
        "source": source,
        "source_version": args.source_version,
        "artifact_type": ARTIFACT_TYPES[source],
        "artifact_ref": artifact_ref,
        "observed_at": observed_at,
    }
    for key in ("run_id", "runtime_agent_id"):
        if getattr(args, key, None):
            link[key] = getattr(args, key)
    return link


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _cmd_evidence(args: argparse.Namespace, client: httpx.Client) -> int:
    from pathlib import Path

    command = args.evidence_command
    if command == "ingest":
        body = {
            "link": _link(args, args.source, args.artifact_ref, args.observed_at or _now()),
            "artifact": _load_payload(args.artifact_file),
            "gate": _load_payload(args.gate) if args.gate else None,
        }
        _print_json(_post_evidence(client, body))
    elif command == "ingest-manifest":
        # Paths are read by this client relative to the manifest; the server never opens files.
        manifest_path = Path(args.manifest_file)
        entries = _load_payload(str(manifest_path)).get("entries", [])
        results = []
        for entry in entries:
            body = {"link": entry["link"], "artifact": None, "gate": None}
            for key in ("artifact", "gate"):
                if entry.get(f"{key}_path"):
                    body[key] = _load_payload(str(manifest_path.parent / entry[f"{key}_path"]))
            results.append(_post_evidence(client, body))
        _print_evidence_results(results)
    elif command == "ingest-sidecar-journal":
        from agenticops_control_tower.adapters import sidecar_journal_decisions

        results = []
        content = Path(args.journal_file).read_text(encoding="utf-8")
        for entry in sidecar_journal_decisions(content):
            reference = entry.decision.get("decision_id") or f"{entry.task_id}:{entry.sequence}"
            link = _link(
                args, "agentic-sidecar", f"decision:{reference}", entry.recorded_at.isoformat()
            )
            results.append(_post_evidence(client, {"link": link, "artifact": entry.decision}))
        _print_evidence_results(results)
    elif command == "history":
        params: dict[str, Any] = {"limit": args.limit}
        if args.source:
            params["source"] = args.source
        response = client.get(f"/agents/{args.agent_id}/evidence/history", params=params)
        _raise_for_status(response)
        _print_json(response.json())
    else:
        response = client.get(
            f"/agents/{args.agent_id}/evidence",
            params={"stale_after_seconds": args.stale_after_seconds},
        )
        _raise_for_status(response)
        _print_json(response.json())
    return 0


def _print_evidence_results(results: list[dict[str, Any]]) -> None:
    records = [result["record"] for result in results]
    _print_json(
        {
            "submitted": len(results),
            "created": sum(1 for result in results if result["created"]),
            "unavailable": sum(
                1 for record in records if record["summary"]["availability"] == "unavailable"
            ),
            "records": records,
        }
    )


def _cmd_posture(args: argparse.Namespace, client: httpx.Client) -> int:
    params: dict[str, Any] = {"stale_after_seconds": args.stale_after_seconds}
    if args.environment:
        params["environment"] = args.environment
    response = client.get("/posture", params=params)
    _raise_for_status(response)
    _print_json(response.json())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agenticops-control-tower")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("AGENTICOPS_API_URL", DEFAULT_API_URL),
        help=f"Control Tower API base URL (default: {DEFAULT_API_URL}, or $AGENTICOPS_API_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("AGENTICOPS_TOKEN"),
        help="API bearer token (or $AGENTICOPS_TOKEN)",
    )
    parser.add_argument("--snapshot", help="Inspect a local fleet snapshot without an HTTP server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the Control Tower HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--database", help="SQLite registry file (or $AGENTICOPS_DATABASE)")
    serve.set_defaults(handler=_cmd_serve, needs_client=False)

    agents = subparsers.add_parser("agents", help="Inspect and register agents")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)

    register = agents_sub.add_parser("register", help="Register an agent from a JSON payload")
    register.add_argument("payload_file", help="Path to a JSON file matching the AgentRecord shape")
    register.set_defaults(handler=_cmd_agents_register, needs_client=True)

    heartbeat = agents_sub.add_parser("heartbeat", help="Send a heartbeat for an agent")
    heartbeat.add_argument("agent_id")
    heartbeat.add_argument(
        "payload_file", help="Path to a JSON file matching the HeartbeatPayload shape"
    )
    heartbeat.set_defaults(handler=_cmd_agents_heartbeat, needs_client=True)

    agents_list = agents_sub.add_parser("list", help="List all registered agents")
    agents_list.add_argument("--status", choices=["healthy", "degraded", "unhealthy", "unknown"])
    agents_list.add_argument("--unhealthy", dest="status", action="store_const", const="unhealthy")
    agents_list.add_argument("--environment")
    agents_list.add_argument("--capability")
    agents_list.add_argument("--missing-capability")
    agents_list.set_defaults(handler=_cmd_agents_list, needs_client=True)

    agents_get = agents_sub.add_parser("get", help="Get one agent by ID")
    agents_get.add_argument("agent_id")
    agents_get.set_defaults(handler=_cmd_agents_get, needs_client=True)

    capabilities = subparsers.add_parser("capabilities", help="Inspect capability inventory")
    capabilities_sub = capabilities.add_subparsers(dest="capabilities_command", required=True)
    capabilities_list = capabilities_sub.add_parser(
        "list", help="List capability versions across all agents"
    )
    capabilities_list.set_defaults(handler=_cmd_capabilities_list, needs_client=True)

    status = subparsers.add_parser(
        "status", help="Fleet health, capability coverage and version rollups"
    )
    status.add_argument("--environment")
    status.set_defaults(handler=_cmd_status, needs_client=True)
    config = subparsers.add_parser("config", help="Read configuration ownership and values")
    config.add_argument("agent_id")
    config.add_argument("capability")
    config.set_defaults(handler=_cmd_configuration, needs_client=True)
    audit = subparsers.add_parser("audit", help="Read configuration action audit")
    audit.add_argument("agent_id")
    audit.set_defaults(handler=_cmd_configuration, needs_client=True)
    actions = subparsers.add_parser("actions", help="Preview, approve and execute bounded actions")
    action_sub = actions.add_subparsers(dest="action_command", required=True)
    for operation in ("preview", "get", "approve", "deny", "revoke", "execute"):
        command = action_sub.add_parser(operation)
        command.add_argument("payload_file" if operation == "preview" else "action_id")
        command.set_defaults(handler=_cmd_configuration, needs_client=True)

    from agenticops_control_tower.evidence import DEFAULT_STALE_AFTER_SECONDS
    from agenticops_control_tower.models import EVIDENCE_SOURCES

    def stale_after_option(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--stale-after-seconds",
            type=int,
            default=DEFAULT_STALE_AFTER_SECONDS,
            help="Evidence observed earlier than this is reported as stale (default: 1 day)",
        )

    evidence = subparsers.add_parser(
        "evidence", help="Push native producer evidence and read history/posture"
    )
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    ingest = evidence_sub.add_parser("ingest", help="Push one native artifact (writer)")
    ingest.add_argument("agent_id")
    ingest.add_argument("source", choices=EVIDENCE_SOURCES)
    ingest.add_argument("artifact_file", help="Native producer JSON artifact")
    ingest.add_argument("--source-version", required=True)
    ingest.add_argument("--artifact-ref", required=True, help="Caller-owned stable reference")
    ingest.add_argument("--observed-at", help="ISO 8601 observation time (default: now)")
    ingest.add_argument("--run-id")
    ingest.add_argument("--runtime-agent-id")
    ingest.add_argument("--gate", help="Existing Evals GateDecision JSON for this report")
    manifest = evidence_sub.add_parser(
        "ingest-manifest", help="Push every entry of a collection manifest (writer)"
    )
    manifest.add_argument("manifest_file")
    journal = evidence_sub.add_parser(
        "ingest-sidecar-journal", help="Push decisions from a Sidecar journal export (writer)"
    )
    journal.add_argument("agent_id")
    journal.add_argument("journal_file")
    journal.add_argument("--source-version", required=True)
    journal.add_argument("--run-id")
    journal.add_argument("--runtime-agent-id")
    history = evidence_sub.add_parser("history", help="Newest evidence records first")
    history.add_argument("agent_id")
    history.add_argument("--source", choices=EVIDENCE_SOURCES)
    history.add_argument("--limit", type=int, default=50)
    agent_posture = evidence_sub.add_parser("posture", help="Per-source posture for one agent")
    agent_posture.add_argument("agent_id")
    stale_after_option(agent_posture)
    for command in (ingest, manifest, journal, history, agent_posture):
        command.set_defaults(handler=_cmd_evidence, needs_client=True)

    posture = subparsers.add_parser("posture", help="Fleet evidence posture by producer")
    posture.add_argument("--environment")
    stale_after_option(posture)
    posture.set_defaults(handler=_cmd_posture, needs_client=True)
    return parser


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    """CLI entry point. Returns a process exit code.

    `client` is an injection point for tests -- pass any `httpx.Client`
    (e.g. `fastapi.testclient.TestClient(create_app())`) to exercise commands
    against an in-process app without a running server. See tests/test_cli.py.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.snapshot:
        from agenticops_control_tower.models import AgentStatus
        from agenticops_control_tower.snapshot import load_snapshot

        if args.command in ("serve", "config", "audit", "actions", "evidence", "posture") or (
            args.command == "agents" and args.agents_command in ("register", "heartbeat")
        ):
            parser.error("--snapshot supports read commands only")
        api = load_snapshot(args.snapshot)
        if args.command == "status":
            _print_json(api.get_status(environment=args.environment).model_dump(mode="json"))
        elif args.command == "capabilities":
            _print_json(api.list_all_capabilities())
        elif args.agents_command == "get":
            _print_json(api.get_agent(args.agent_id).model_dump(mode="json"))
        else:
            records = api.list_agents(
                status=AgentStatus(args.status) if args.status else None,
                environment=args.environment,
                capability=args.capability,
                missing_capability=args.missing_capability,
            )
            _print_json([record.model_dump(mode="json") for record in records])
        return 0

    if not args.needs_client:
        return int(args.handler(args))

    if client is not None:
        if args.token:
            client.headers["Authorization"] = f"Bearer {args.token}"
        # Caller-supplied client (tests): don't close something we don't own.
        return int(args.handler(args, client))

    with _client(args.api_url) as owned_client:
        if args.token:
            owned_client.headers["Authorization"] = f"Bearer {args.token}"
        return int(args.handler(args, owned_client))


def run() -> None:
    """Console-script entry point (`agenticops-control-tower`)."""
    sys.exit(main())


if __name__ == "__main__":
    run()
