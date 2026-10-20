# Live operations — Tower 0.8.0

Tower evaluates locally stored, explicitly attributed telemetry every 30 seconds
while the HTTP application's lifespan is running. `create_app(detection_interval_seconds=0)`
disables the worker; a trusted scheduler can instead call `POST /alerts/evaluate`.
The internal actor is `tower-detector`. Detection creates alerts and incidents,
never approvals, runtime controls or recovery execution. No LLM or sibling import
is required. Scanner failures are logged and retried on the next interval.

## Rules and freshness

`api.operations.policy = DetectionPolicy(...)` configures trusted host policy;
both freshness and heartbeat windows default to 300 seconds (range 1–86400).

| Rule | Condition | Meaning |
| --- | --- | --- |
| `lens.failed` | Latest native Lens record is an available failed `run`, observed within the freshness window and not in the future | Critical alert and idempotent recovery incident; cause unconfirmed |
| `heartbeat.stale` | Last heartbeat, or registration when none exists, is overdue | Warning; reported health unchanged |
| `evidence.stale` | Latest pushed record for a producer is older than the window | Warning; native verdict unchanged |
| `evidence.missing` | An installed producer capability has no pushed records | Warning; uninstalled optional packages do not cause alerts |

The latest observation per producer/deployment drives each scan. This is a
current-posture detector, not a lossless stream processor: a newer run or diagnosis
can supersede a failed run before a scan. Delayed pushes older than the window,
future timestamps and invalid native artifacts never create recovery incidents.
Unavailable projections remain visible in evidence posture. There is no remote
polling, arbitrary rule expression evaluation, automatic evidence fetching or
external notification delivery. The alert feed and console are the notification
surfaces in this release.

Alerts deduplicate by deployment, environment, rule, source and (for failures)
observation ID. Repeated scans preserve acknowledgement and first-seen time.
Absent conditions clear alerts; cleared warning conditions can reopen with a new
acknowledgement lifecycle. Append-only audit events preserve create, acknowledge,
clear and reopen history. Older scans cannot regress a newer saved scan. Retrying
a scan after an interrupted incident/alert write safely reuses the incident.

Correlation keys group same-source, explicitly same-run alerts across agents
**within an environment**. A shared run ID is a correlation hint, not a causal
finding or a cross-environment incident merge. Missing run IDs stay deployment
local. Each recovery incident and its approvals remain scoped to one deployment.
Clearing an alert never resolves its incident; recovery still requires the
existing probe, fresh native Lens success and same-run passing Evals gate.

## Operator workflow

```bash
export AGENTICOPS_TOKEN=writer-token  # or pass --token explicitly
agenticops-control-tower --token writer-token alerts evaluate
agenticops-control-tower --token reader-token alerts list --active-only --environment staging
agenticops-control-tower --token writer-token alerts acknowledge ALERT_ID
agenticops-control-tower --token reader-token incidents view INCIDENT_ID
uv run python examples/live_operations.py
```

HTTP reads: `GET /alerts?environment=staging&active_only=true`,
`GET /incidents?environment=staging`, `GET /incidents/{id}/view`.
Writes: `POST /alerts/evaluate`, `POST /alerts/{id}/acknowledge`.
Readers cannot evaluate or acknowledge. Incident reads use the existing
configured-credential contract; anonymous development inventory remains usable.
HTTP identities are server-derived `http-reader`, `http-writer`, `http-approver`;
tokens represent deployment-wide roles, not named end users. Trusted Python
`Operator.agent_ids` limits reads, scans, acknowledgements and joined views.
Offline inventory snapshots do not contain live alerts or incidents.

## Incident console and joined audit

Connect to `/console/` with a reader token. Active alerts, acknowledgements and
an incident queue refresh every 30 seconds. Select an incident to inspect its
inventory, reported health, evidence posture, findings/citations, plan, approval
state, execution claims/receipts and recovery checks. All console requests remain
GET-only; actions use the same authenticated API/CLI as before.

`incident_view` joins the original detection (even if evidence was pruned),
explicit same-run native evidence within that deployment, the incident's durable
events, retained deployment configuration/bulk audit, and alert lifecycle audit.
Each timeline entry includes time, actor, source and event. Configuration and
alert audit are deployment context and may include changes unrelated to the
incident; `change_scope` labels this explicitly. Policy decisions remain native
Sidecar evidence. Requested commands and actual connector acknowledgements retain
distinct events; a request is never proof of containment.

Lens integrity is `not_verified` and coverage is `not_assessed`, separately from
reported health and evidence freshness. Tower does not infer cryptographic
integrity, execution completeness or exact root cause from timestamps and links.
Native projections omit unsupported raw payloads; use authorized producer tools
for deeper inspection. Approval/recovery evidence remains in the embedded incident
even when its run differs from the detection run.

## Persistence and package boundaries

Use `AGENTICOPS_DATABASE` / `create_app(database_path=...)` for registry, evidence,
configuration, incidents, scans and alerts in one local SQLite database. Without
it all state is process-local. SQLite remains a single-host deployment model;
multiple workers may scan, but writes and incident identities deduplicate. Audit
is retained without automatic pruning; it is not an independently tamper-evident
ledger. No distributed leader election, alert retention policy or remote telemetry
subscription is supplied.

All sibling extras keep their current compatible ranges. Lens supplies native
runs; Evals supplies report/gate verdicts; Sidecar supplies native decisions and
runtime enforcement; Chaos supplies resilience evidence; MCP retains existing
`tower.*` tools. New alert/view endpoints are Tower API/CLI surfaces, not new MCP
tools. AIOS remains draft; these are Tower-local contracts. See
[ecosystem compatibility](tower-0.8-compatibility.md).
