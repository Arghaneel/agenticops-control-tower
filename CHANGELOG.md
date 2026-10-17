# Changelog

## [Unreleased]

## 0.5.2

Released 2026-10-17.

### Fixed

- Accept Lens diagnosis schema 1.1 alongside 1.0 after Sidecar supervision timeline
  events were added in Lens 0.7.1. Unknown schema versions remain unavailable;
  producer governance outcomes remain separate from deployment health.
- Document Sidecar 0.8 shared/exclusive scope and evidence integration boundaries.


## 0.5.1

Released 2026-10-13.

### Added

- Native AgenticLens 0.7.0 diagnosis reports as Lens evidence
  (`artifact_type: diagnosis_report`). The projection keeps run and trace IDs,
  run status, task success, taxonomy and engine versions, diagnosis counts,
  and Lens's attribution (status, faulty step and agent, category,
  confidence). Diagnoses, span evidence and timelines stay in Lens.
- Lens posture tallies `attribution_counts` and `faulty_agents` next to run
  `status_counts`.
- `evidence ingest` picks `diagnosis_report` automatically for Lens artifacts
  with an `engine_version` field.
- `examples/evidence/lens_diagnosis.json` sample and tests, including one
  against the real `agenticlens.diagnosis` package.

### Changed

- Sample registrations and heartbeats report `agenticlens` 0.7.0. Checked
  against Lens 0.7.0 and Chaos 0.5.3.
- The optional `agenticlens` extra requires `>=0.7`; the lock resolves Lens
  0.7.0 and Chaos 0.5.3, so the ecosystem CI job tests the diagnosis reader.

## 0.5.0

Released 2026-10-13.

### Added

- Push-based ecosystem evidence ingestion through `ControlTowerAPI.ingest_evidence`,
  `POST /evidence` (writer) and CLI `evidence ingest`, `ingest-manifest` and
  `ingest-sidecar-journal`. Retries of one attributed observation are idempotent.
- Durable evidence history in memory or the shared SQLite database, with
  future-time rejection, 1 MiB HTTP body limit and Python pruning. Only validated
  projections are stored; unavailable results are kept with their reason.
- Agent and fleet evidence posture (`GET /agents/{id}/evidence`, `GET /posture`,
  CLI `evidence posture` and `posture`): fresh/stale/missing freshness, latest
  record, recent counts and tallies of native producer values. Producer outcomes
  never change reported health and no verdict is recomputed.
- `GET /agents/{id}/evidence/history` and CLI `evidence history`.
- Lens run projection of trace ID, timing, task success, error type, tool names
  and failed spans, without span payloads or error messages.
- `sidecar_journal_decisions()` for Sidecar JSON, export-array and JSONL journals.
- Read-only console fleet posture panel and per-agent evidence table.
- Offline snapshots accept an `evidence` list, evaluated as of `captured_at`.
- Evidence guide, native sample artifacts, collection manifest, Python push
  example and a CI job against published sibling extras.

### Changed

- `GET /agents/{id}/evidence` returns per-producer posture instead of a fixed
  `unavailable` readiness message.
- Unavailable evidence reasons name the failing native field without echoing values.
- Optional sibling floors: Lens 0.6, Chaos 0.5 and MCP 0.3.4 (Evals 0.7 and
  Sidecar 0.7 unchanged). Checked against Lens 0.6.1, Evals 0.7.1, Sidecar 0.7.0
  and Chaos 0.5.1.

### Limits

- Tower does not pull from producer services or fetch artifact references.
  Producers share the writer token; per-producer credentials, AIOS mapping,
  journal integrity verification and automatic retention remain planned.

## 0.4.0

Released 2026-10-12.

### Added

- Tower-owned desired configuration with explicit mirrored/unsupported ownership.
- Bounded action previews, independent approvals, denial, expiry, revocation,
  revision matching and one-use execution; deployment-scoped Python operators.
- Transactional SQLite configuration, action state and audit persistence,
  including rejected commands; concurrent stale actions cannot overwrite state.
- Configuration/action/audit HTTP and CLI surfaces with separate approval tokens.
- Configuration examples, safety regression tests and updated optional sibling
  dependency floors for Lens 0.5, Sidecar 0.7, Chaos 0.4 and MCP 0.3.1.

### Limits

- Desired settings are local to Tower. Runtime reconfiguration, stop/revoke
  transport, remote partial-failure reconciliation and console writes remain planned.
- Local writes are atomic: storage errors roll back settings, approval consumption
  and success audit together. Result contracts reserve remote failure/rollback states.

## 0.3.1

Released 2026-10-12.

### Fixed

- Journal readback accepts direct native JSON export arrays in addition to
  recording objects and JSONL, with regular-suite regression coverage.

- Native Sidecar decision summaries preserve optional decision IDs and trigger
  details alongside causal links. Legacy artifacts remain compatible.
- Added Sidecar v0.7 journal readback examples and actual-producer tests for all
  seven outcomes, causal identity and deployment-health separation.

### Documentation

- Expanded the command-center roadmap with evidence-backed copilot investigation,
  a first human-approved incident-to-recovery scenario (v0.6.x), live incident
  views (v0.8), and automated runbooks with recovery verification (v0.9).

- Added customer-managed token generation and rotation instructions, local/cloud
  console hosting guidance, and local startup/HTTPS proxy examples.

## 0.3.0

### Fixed

- Reject route-unsafe agent IDs at registration and snapshot validation; cover
  accepted IDs through real HTTP detail, heartbeat and evidence routes.
- Reconcile README implementation status with the shipped read-only console.

### Added

- Packaged read-only AgenticOps Console at `/console/`, using existing authenticated
  APIs for health, filtered inventory, coverage, versions and agent details.
- Shared PEP 440 minimum-version assessments and authorized `GET /versions`.
- Agent evidence-readiness read endpoint and console view that explicitly show
  unavailable evidence collection and planned incident/remediation workflows.
- Memory-only console credentials, disconnect/failed-refresh clearing, responsive
  accessible controls and a restrictive content security policy.

## 0.2.1

### Added

- Native Lens, Evals, Sidecar and Chaos evidence readers with explicit deployment
  attribution, unavailable results, and optional actual-producer contract tests.
- Ecosystem ownership/correlation documentation and aligned example versions.
- Optional durable SQLite registry with transactional heartbeat updates.
- Reader/writer bearer authorization for HTTP routes and CLI token support.
- Shared fleet status, capability coverage/version rollups, HTTP and CLI filters.
- Offline snapshot CLI reads and milestone acceptance tests.

### Fixed

- Reconciled Python registration, heartbeat and discovery APIs with snapshot
  loading and existing models; unknown agents now return HTTP 404.
- Updated roadmap, audit and operator documentation to reflect completed v0.1/v0.2.


### Added

- HTTP API (`agenticops_control_tower.api.http.create_app()`, optional `api`
  extra) implementing the v0.1 roadmap's suggested surface: `POST
  /agents/register`, `POST /agents/{id}/heartbeat`, `GET /agents`, `GET
  /agents/{id}`, `GET /capabilities` (aggregated across all agents).
- Operator CLI (`agenticops-control-tower` console script, optional `api`
  extra): `serve`, `agents register|heartbeat|list|get`, `capabilities list`.
- `ControlTowerAPI.register()`, `.heartbeat()`, and `.list_all_capabilities()`
  facade methods backing the HTTP layer.
- `examples/sample_agent_registration_kubernetes.json`, a second example
  registration payload (`kubernetes`/`crewai`) alongside the existing
  `aws-lambda`/`langgraph` one.
- `tests/test_http_api.py` and `tests/test_cli.py` (skip automatically
  without the `api` extra installed).

## 0.0.1

- Initial repository scaffold
- Concept-stage README and roadmap
- Package layout, tests, and CI/release workflows
