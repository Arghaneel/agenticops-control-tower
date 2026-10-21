# Troubleshooting

## Installation

| Symptom | Cause and fix |
| --- | --- |
| `agenticops-control-tower: error: argument command: invalid choice` for `--snapshot`, `posture`, `alerts` or `incidents` | You may have an older installation (for example **0.2.0**), which predates these commands. Check with `python -c "import agenticops_control_tower as t; print(t.__version__)"` and [upgrade to 0.8.0](getting-started.md#install). |
| `This command talks to the Control Tower HTTP API and needs httpx` | Server-mode CLI commands need the `api` extra: install `".[api]"`. Offline `--snapshot` reads do not. |
| `serve` fails with `ModuleNotFoundError: No module named 'fastapi'` (or asks for `uvicorn`) | Install the `api` extra. |
| `ValueError: Approval token must differ from reader and writer tokens` at startup | Generate a separate value for `AGENTICOPS_APPROVAL_TOKEN`. |

## Snapshot mode

| Symptom | Cause and fix |
| --- | --- |
| `error: --snapshot supports read commands only` | Snapshots are read-only. `serve`, `agents register/heartbeat`, `evidence ingest*`, `config`, `audit`, `actions`, `bulk`, `alerts` and `incidents` need a server. |
| `AgentNotFoundError: Agent 'X' is not registered` (with a traceback) | `agents get` was given an ID that is not in the snapshot. Run `agents list` to see the IDs. |
| Sample evidence shows as `fresh` offline but `stale` on a server | Expected. Offline posture is evaluated at the snapshot's `captured_at`; a live server uses the current time, and the samples are dated 2026-08-15. |

## Server and console

| Symptom | Cause and fix |
| --- | --- |
| `Control Tower API returned 401: Bearer token required` | Tokens are configured on the server; pass `--token` or set `AGENTICOPS_TOKEN`. |
| `Control Tower API returned 401: Invalid bearer token` | The value differs from the running server's. Exported variables are not shared between terminals; copy it from your secret storage. |
| `Control Tower API returned 403: Writer token required` | Registration, heartbeats and evidence pushes need the **writer** token. |
| Configuration, bulk or incident commands return 403 without tokens | These routes refuse anonymous access even in local development. Configure tokens. |
| Inventory disappears after a restart | Start `serve` with the same `--database` file. Without it, storage is in memory. |
| Console loads but shows no agents | Nothing is registered on this server yet; register an agent and select **Connect / refresh**. |
| Console works on your computer but not for a colleague | `localhost` means the browser's own computer. See [hosting](hosting.md) for private-network and HTTPS setups. |
| `POST /evidence` returns 411 or 413 | The body must have a `Content-Length` and be at most 1 MiB. |

## Alerts and evidence

| Symptom | Cause and fix |
| --- | --- |
| A failed Lens run did not raise an alert | Detection uses the **latest** Lens record per deployment within the 300-second freshness window. A newer run, an older observation or a future timestamp does not alert. See [live operations](live-operations.md). |
| Alerts appear but the agent still reports `healthy` | By design: health is agent-reported and evidence never changes it. |
| Evidence posture says `missing` | No artifact has been pushed for that producer and deployment. Tower never fetches evidence. |
| Evidence posture says `unavailable` | The pushed artifact could not be read as the producer's native shape; check `source`, `artifact_type` and `source_version` against [ecosystem alignment](ecosystem-alignment.md). |

Still stuck? Open an
[issue on GitHub](https://github.com/DeepAgentLabs/agenticops-control-tower/issues)
with the command, the full output and your version.
