# agenticops-control-tower

**An AI-native operations command center and unified control plane for autonomous agents and the DeepAgentLabs ecosystem.**

> AgenticLens observes. Agentic Evals evaluates. Agentic Sidecar supervises. Agentic Chaos tests. Agentic
> MCP connects. Control Tower operates.

## Status

**Current version: 0.6.0. Phases 6 and 6A ship together in this release.** The registry,
HTTP API and CLI support SQLite persistence, reader/writer bearer authorization,
shared fleet health and capability coverage, agent filters, and offline snapshots.
Tower-owned configuration uses approved actions, and pushed Lens, Evals, Sidecar
and Chaos evidence is stored and shown as posture. The read-only web console is
served at `/console/`. See [ROADMAP.md](ROADMAP.md) for published milestone status,
[implementation evidence and operational limits](ROADMAP.md#implementation-evidence-and-operational-limits),
and the build plan.

## Investigation and approved recovery (0.6.0)

Phases 6 and 6A are one release: an authenticated MCP connector, an operations
investigation prompt over cited evidence, durable incidents, exact-preview human
approval and one bounded staging dependency runbook. A successful command awaits
fresh Lens success, a same-run passing Evals gate and a probe; failed verification
escalates. SQLite execution claims prevent replay after duplicates or crashes.
Thin Sidecar stop/restart and native MCP issuer revocation adapters keep emergency
control independent of model approval. Production runtime adapters remain planned.

See the [operator guide](docs/incident-recovery.md), [MCP setup](docs/mcp-connector.md)
and [native-producer walkthrough](examples/incident_recovery.py). The console
remains read-only. Base Tower and MCP stay usable without sibling packages.

## Ecosystem evidence posture (v0.5)

Producers or pipelines push native Lens runs, Evals reports and gates, Sidecar
decisions and Chaos reports to Tower with an explicit deployment attribution.
Tower stores the validated projection and reports, per deployment and per
producer, whether evidence is **fresh, stale or missing**, plus counts of native
outcomes (run status, failed tool names, gate results, decision outcomes and
risk, chaos experiments). Retries are idempotent. Producer outcomes never
change reported health, and Tower never recomputes a verdict.

```bash
agenticops-control-tower evidence ingest-manifest examples/evidence/manifest.json
agenticops-control-tower evidence ingest payment-agent agenticlens run.json \
  --source-version 0.7.0 --artifact-ref lens:run:r1 --run-id r1
agenticops-control-tower evidence ingest payment-agent agenticlens diagnosis.json \
  --source-version 0.7.0 --artifact-ref lens:diagnosis:r1 --run-id r1
agenticops-control-tower evidence ingest-sidecar-journal payment-agent journal.json --source-version 0.7.0
agenticops-control-tower evidence posture payment-agent
agenticops-control-tower evidence history payment-agent --source agentic-sidecar
agenticops-control-tower posture --environment production
agenticops-control-tower --snapshot examples/sample_fleet_snapshot.json posture
```

HTTP: `POST /evidence` (writer), `GET /agents/{id}/evidence`,
`GET /agents/{id}/evidence/history` and `GET /posture` (reader). Python:
`ingest_evidence`, `evidence_history`, `agent_posture` and `fleet_posture` on
`ControlTowerAPI`; see `uv run python examples/push_ecosystem_evidence.py`.
Collection is push-only; Tower never fetches artifact references. Read the
[evidence posture guide](docs/evidence-posture.md) for rules, limits and storage.

## Controlled configuration (v0.4)

Tower-owned desired configuration supports preview → independent approval →
execution, with expiry, revision checks, revocation, deployment scopes and durable
SQLite audit records. Runtime-owned settings stay mirrored or unsupported;
changing desired settings does not claim to reconfigure a sibling runtime.

See [configuration and approval guide](docs/configuration.md) and run
`uv run python examples/controlled_configuration.py` for a complete Python flow.
Use `config AGENT CAPABILITY`, `actions preview REQUEST.json`, `actions get ID`,
`actions approve|deny|revoke|execute ID`, and `audit AGENT` from the CLI.
HTTP writes require a writer token and approvals require a separate
`AGENTICOPS_APPROVAL_TOKEN`. The console remains read-only.

## Read-only console (v0.3)

Run `agenticops-control-tower serve --database registry.sqlite --port 8000`,
then open **http://localhost:8000/console/**. The `api` extra includes the
console; no Node build or separate UI server is required.

Enter the server's reader token and select **Connect / refresh** (leave it blank
for anonymous local development). The console shows reported fleet health,
searchable/filterable inventory, environment-scoped capability coverage,
versions, heartbeat timestamps and agent metadata. Select a capability and enter
an optional minimum version to identify outdated installations using PEP 440;
missing capabilities and invalid reported versions remain distinct. This minimum
is your policy, not an inferred latest release. Refresh is manual.

The **Ecosystem evidence posture** panel shows fresh, stale and missing
evidence per producer for the selected environment. Select an agent to inspect
details and its per-producer evidence: freshness, latest record, recent window
and native tallies. Evidence-led incident investigation and approved deterministic staging recovery ship in 0.6.0; production remediation remains planned.
Configuration approvals are available through API/CLI.

The public HTML shell contains no fleet data. Every data request uses the same
reader/writer bearer authorization as API and CLI reads. Credentials are retained
only in page memory, cleared by **Disconnect** or page reload; failed refreshes
clear the displayed inventory. Use HTTPS when serving bearer-authenticated
traffic remotely. The console sends only GET requests.

Additional read endpoints: `GET /versions?capability=agenticlens&minimum_version=0.5.0`
(optionally `environment=staging`), `GET /agents/{agent_id}/evidence` (per-producer
posture) and `GET /posture` (fleet posture). Version policy is also available as
`ControlTowerAPI.assess_versions(capability, minimum_version, environment=...)`.

## Generate access tokens and host your console

Customers self-hosting this PyPI package generate and manage their own tokens;
no DeepAgentLabs account or token service is needed. Generate a reader value
with Python's standard library (Bash):

```bash
export AGENTICOPS_READ_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

Alternatively use `openssl rand -hex 32`; use `python3` if that is your Python
command. Configure a separate `AGENTICOPS_WRITE_TOKEN` for registration and
heartbeats. Save both in secret storage and reuse them when restarting the server.
Users paste the reader value into the console and select **Connect / refresh**.
These are shared deployment credentials, not user accounts. With only a reader
configured, writes are rejected; with neither token configured, access is anonymous.

- [Authentication guide](docs/authentication.md): generation, PowerShell setup,
  reader/writer roles, CLI access and rotation.
- [Hosting guide](docs/hosting.md): local `http://localhost:8000/console/`,
  private-network access and cloud `https://<your-hostname>/console/` links.
- [Examples](examples/README.md): local startup and an HTTPS reverse-proxy template.

The console and API run in the same Python service. Cloud deployments need
HTTPS ingress, configured tokens and persistent storage for durable inventory.
Installing from PyPI alone does not create a hosted URL. Localhost links work
only on the computer running the browser.

## Command-center vision

The intended workflow is **detect failure → investigate with live evidence →
explain the cause → recommend remediation → obtain human approval → execute a
runbook → verify recovery**. An operations copilot uses MCP tools to correlate
Lens traces, tool calls, prompt versions, dependencies and sibling evidence.
Diagnoses cite evidence and distinguish confirmed causes from hypotheses.
Tower owns incident coordination; the sibling packages retain their engines.

The first complete loop ships in 0.6.0 for the deterministic staging runtime.
The roadmap adds broader live incident views in v0.8 and
reusable automated runbooks in v0.9. See [the command-center roadmap](ROADMAP.md#product-vision-ai-native-operations-command-center).

## Quickstart

```bash
pip install agenticops-control-tower[api]   # fastapi/uvicorn/httpx for the HTTP API + CLI

# Customers generate their own tokens. Save and reuse these values on restart.
export AGENTICOPS_READ_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export AGENTICOPS_WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export AGENTICOPS_TOKEN="$AGENTICOPS_WRITE_TOKEN"

# Terminal 1: durable registry (file survives server restarts)
agenticops-control-tower serve --database registry.sqlite --port 8000

# Terminal 2: obtain the SAME writer token from your deployment's secret storage.
# Exports in Terminal 1 are not automatically available in Terminal 2.
export AGENTICOPS_TOKEN='paste-your-generated-writer-token-here'
# Register an agent, send a heartbeat, and inspect the fleet
agenticops-control-tower agents register examples/sample_agent_registration.json
echo '{"status":"healthy","capabilities":{"agenticlens":"0.7.0"}}' > heartbeat.json
agenticops-control-tower agents heartbeat payment-agent heartbeat.json
agenticops-control-tower agents list
agenticops-control-tower capabilities list
agenticops-control-tower status
agenticops-control-tower agents list --unhealthy
agenticops-control-tower agents list --environment staging --missing-capability agentic-sidecar
agenticops-control-tower --snapshot examples/sample_fleet_snapshot.json status
# Push native producer evidence and read posture (v0.5)
agenticops-control-tower evidence ingest-manifest examples/evidence/manifest.json
agenticops-control-tower posture
```

`AGENTICOPS_TOKEN` authenticates the CLI. Reader tokens permit GET routes;
writer tokens permit reads, registration and heartbeats. With only a reader
token configured, writes are rejected. With no server tokens configured, access
is anonymous for local development. `AGENTICOPS_DATABASE` also selects SQLite
storage; omit it and `--database` for in-memory mode.

Health rollups count agent-reported `healthy`, `degraded`, `unhealthy`, and
`unknown` states. They do not infer failures from heartbeat age. Capability
versions are reported inventory, not an upgrade recommendation. New agent IDs
must start with an ASCII letter or digit and contain only ASCII letters, digits,
dots, underscores and hyphens (e.g. `payment-agent_1.0`).
Slashes, percent escapes, whitespace and dot-only IDs are rejected by registration
and snapshot validation. Use the free-form `name` field for display labels.
Existing stored records are not renamed automatically. Re-registering
an ID replaces its record; heartbeats merge metadata and increment its count.

Without the `api` extra, `pip install agenticops-control-tower` still gives
you the underlying Python control model (`ControlTowerAPI`, `AgentRegistry`,
`CapabilityDiscoveryService`) with zero web-framework dependency — the HTTP
server and CLI are optional surfaces over the same model, not the only way to
use it.

## Contents

- [Quickstart](#quickstart)
- [Why this exists](#why-this-exists)
- [What Control Tower is](#what-control-tower-is)
- [What it is not](#what-it-is-not)
- [Architecture](#architecture)
- [Control Tower surfaces](#control-tower-surfaces)
- [Human operators and AI operators](#human-operators-and-ai-operators)
- [Runtime and framework position](#runtime-and-framework-position)
- [The DeepAgentLabs ecosystem](#the-deepagentlabs-ecosystem)
- [Initial scope](#initial-scope)
- [Roadmap](#roadmap)

## Why this exists

The DeepAgentLabs projects each answer a different operational question:

- **AgenticLens** asks: what happened, why did it happen, and what should I fix?
- **Agentic Evals** asks: how well did the output meet expectations, and did it pass the release gate?
- **Agentic Sidecar** asks: should this action happen right now, given the
  user's intent and current risk?
- **Agentic Chaos** asks: what breaks under stress, failure, and silent
  degradation?
- **Agentic MCP** asks: how do hosts and agents access these capabilities
  through one MCP-native surface?

What is still missing is the layer above them:

> What is deployed, where is it running, which capabilities are enabled, what
> is unhealthy, and how do I operate all of it from one place?

That missing layer is the job of `agenticops-control-tower`.

## What Control Tower is

Control Tower is intended to be the **runtime-agnostic, framework-agnostic
operations layer** for teams running multiple agents and multiple
DeepAgentLabs capabilities.

At a high level, it should eventually provide:

- a central agent registry
- capability discovery across agents and environments
- health and status visibility
- centralized configuration for supported capabilities
- a unified control API
- a human CLI
- a web console for operators

The key distinction is that Control Tower is **not just a dashboard**. The
dashboard is only one interface to the underlying control plane.

## What it is not

- **Not a replacement for Agentic Evals.** Evals owns scoring and release-gate
  evaluation; Control Tower reads the resulting evidence.
- **Not a replacement for AgenticLens.** Control Tower may surface Lens
  insights, but Lens remains the observability and analysis engine, composing Evals for scoring.
- **Not a replacement for Agentic Sidecar.** Control Tower may surface
  Sidecar decisions and governance posture, but Sidecar remains the
  decision-time supervision layer.
- **Not a replacement for Agentic Chaos.** Control Tower may orchestrate or
  summarize chaos posture, but Chaos remains the resilience-testing engine.
- **Not the MCP layer itself.** Agentic MCP remains an independent package
  and should be able to connect both to individual DeepAgentLabs capabilities
  and to Control Tower.
- **Not tied to one runtime or one framework.** The control plane should sit
  above LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, AWS AgentCore-style
  workloads, MCP-native agents, and custom Python systems rather than
  assuming one execution model.
- **Not the full architecture yet.** The concept doc describes a broader end
  state than what's built so far — see [Status](#status) for what's real
  today (registry, discovery, HTTP API, CLI, read-only console, approved
  desired configuration, evidence posture) versus [ROADMAP.md](ROADMAP.md)
  for implemented investigation/recovery scope and the build order ahead
  (bulk operations, live incident views, reusable runbooks).

## Architecture

The ecosystem boundary should stay crisp:

```text
Control Tower = OPERATE
Agentic MCP   = CONNECT
AgenticLens   = OBSERVE
Agentic Evals = EVALUATE
Agentic Sidecar = SUPERVISE
Agentic Chaos = TEST
AI Operations Specification = STANDARDIZE
```

Conceptually:

```text
                   Human operators           AI operators
                          |                       |
                  Console / CLI / API        Agentic MCP
                          |                       |
                          +-----------+-----------+
                                      |
                                      v
                         DeepAgent Control Tower
                                      |
             +---------------+--------------+---------------+
             |               |              |               |
             v               v              v               v
         AgenticLens    Agentic Evals  Agentic Sidecar  Agentic Chaos
```

Control Tower's role is to centralize operations across agents and
capabilities, not to absorb the implementation logic of the sibling projects.

## Control Tower surfaces

The concept doc points to five main product surfaces:

- **Agent Registry**: inventory of known agents, runtimes, frameworks,
  environments, capability versions, and last-seen status
- **Capability Discovery**: detect which DeepAgentLabs packages and features
  are present on each agent wherever automatic discovery is technically
  feasible
- **Configuration**: centralized configuration and policy updates for
  supported capabilities
- **Unified Control API**: one programmatic interface over inventory, health,
  capability status, and supported operations
- **AgenticOps Console**: the human-facing dashboard over the same control
  plane used by the API and CLI

The CLI should be a first-class interface, not an afterthought. The same is
true for AI-facing operation through Agentic MCP once the underlying control
API exists.

## Human operators and AI operators

This project is unusual in that it has two equally important operator models:

- **Humans** should be able to use a console, CLI, or API to inspect and
  operate agents across environments.
- **AI systems** should be able to use Agentic MCP to inspect and operate the
  same control plane through an MCP-native interface.

That separation matters:

- Control Tower does **not** require MCP
- MCP does **not** require Control Tower
- when used together, MCP becomes the AI-native interface to the control
  plane

## Runtime and framework position

Control Tower should be:

- **runtime agnostic**: local Python, containers, VMs, Kubernetes,
  serverless, cloud-specific runtimes, and on-prem systems are all valid
  targets
- **framework agnostic**: LangGraph, CrewAI, AutoGen, OpenAI Agents SDK,
  custom harnesses, MCP-based agents, and future frameworks should all fit
  the model
- **modular**: teams should be able to adopt a single DeepAgentLabs
  capability without adopting the entire stack

That means deployment packaging is an implementation choice, not an
architectural dependency.

## The DeepAgentLabs ecosystem

Control Tower only makes sense if the package boundaries stay clear:

| Project | Role |
| --- | --- |
| `agenticlens` | Observe |
| `agentic-evals` | Evaluate |
| `agentic-sidecar` | Supervise |
| `agentic-chaos` | Test |
| `deep-agentic-core-mcp` | Connect |
| `ai-operations-spec` | Standardize |
| `agenticops-control-tower` | Operate |

- **Agentic Evals** remains the standalone scoring and release-gate engine
- **AgenticLens** remains package-first observability, evaluation workflows, and
  operational intelligence
- **Agentic Sidecar** remains package-first supervision and governance
- **Agentic Chaos** remains package-first resilience and fault injection
- **Agentic MCP** remains the MCP-native access layer
- **AI Operations Specification** remains the shared operational contract
- **Control Tower** becomes the centralized operate/manage layer across them

This repository should therefore stay focused on:

- inventory and registry concerns
- control-plane APIs
- capability discovery contracts
- health and readiness visibility
- centralized operations and configuration
- multi-agent, multi-environment control-room workflows

It should not quietly turn into a duplicate implementation of the sibling
projects.

## Initial scope

The concept doc describes a very broad end state. A good first implementation
needs to be much narrower.

The first usable version should likely prove four things only:

1. agents can register and heartbeat — **done**, with optional SQLite persistence
2. the system can discover installed DeepAgentLabs capabilities and versions
   — **done**, from agent-reported heartbeat data (not automatic detection)
3. operators can inspect that inventory through a simple API and CLI —
   **done**, via the optional `api` extra (see [Quickstart](#quickstart))
4. the same inventory is surfaced in a console over the same underlying
   control model — **done**, at `/console/` (v0.3)

That core is implemented as a Python API with optional SQLite storage.

## Current `v0.5` Surface

The package currently exposes:

- `register_agent(...)`
- `record_heartbeat(...)`
- `list_agents(...)`
- `get_agent(agent_id)`
- `list_capabilities()`
- `get_agent_capabilities(agent_id)`
- `get_status(...)`
- `assess_versions(capability, minimum_version, ...)`
- `config` (desired configuration, actions and audit)
- `summarize_evidence(link, artifact, gate=...)` (no storage)
- `ingest_evidence(request)`, `evidence_history(agent_id, ...)`
- `agent_posture(agent_id, ...)`, `fleet_posture(...)`

The operator CLI is now available as:

- `agenticops-control-tower agents list`
- `agenticops-control-tower agents get <agent-id>`
- `agenticops-control-tower capabilities list`
- `agenticops-control-tower status`
- `agenticops-control-tower config|audit|actions ...`
- `agenticops-control-tower evidence ingest|ingest-manifest|ingest-sidecar-journal|history|posture ...`
- `agenticops-control-tower posture`

The CLI talks to the HTTP API or reads a fleet snapshot with `--snapshot`.
Both paths use the same status and inventory model.

Example registration payloads are included for two runtime styles:

- [`examples/sample_agent_registration.json`](examples/sample_agent_registration.json)
- [`examples/sample_agent_registration_container.json`](examples/sample_agent_registration_container.json)
- [`examples/sample_fleet_snapshot.json`](examples/sample_fleet_snapshot.json) (includes evidence)
- [`examples/evidence/manifest.json`](examples/evidence/manifest.json) (native producer artifacts)

That is enough to validate the control-plane idea without pretending the full
dashboard, configuration orchestration, and cross-agent operations engine
already exist.

## Roadmap

The build plan is in [ROADMAP.md](ROADMAP.md). In short, the intended order
should be:

- start with a narrow registry and discovery core
- add a real control API and CLI before building the dashboard
- surface Lens, Evals, Sidecar, and Chaos data gradually rather than simulating a
  complete integration layer (v0.5 adds pushed evidence posture)
- add MCP connectivity to Control Tower after the underlying control surfaces
  are real

If you want the full architectural reasoning behind those choices, read the
concept doc first and the roadmap second.

## Ecosystem evidence alignment

Control Tower has thin Python readers for native Lens Runs and diagnosis
reports (AgenticLens 0.7.0: faulty step and agent, attribution confidence,
failure categories), Evals reports and
gate decisions, Sidecar Decisions, and Chaos Reports. Supply an explicit
`EvidenceLink` to `ControlTowerAPI.summarize_evidence()` to attribute an artifact
to an existing registered deployment. The result preserves producer outcomes
and never changes fleet health. Invalid, unsupported or missing artifacts
return `unavailable`; unknown deployment IDs raise `AgentNotFoundError`.

v0.5 adds push-based ingestion, durable history and posture views across
Python, HTTP, CLI, snapshots and the console; see
[evidence posture](docs/evidence-posture.md). Pull collection from producer
services is not implemented. AIOS is draft; native artifacts and Tower's link contract do not establish
AIOS conformance. See [the evidence contract](docs/ecosystem-alignment.md) and
[the runnable example](examples/inspect_ecosystem_evidence.py).


### Console DOM acceptance checks

Python console/API checks run with `make check`. Optional Node DOM checks exercise
rendering, safe text handling, filtering, evidence posture, details, credential retention on refresh,
failed-refresh clearing, disconnect and read-only network requests:

```bash
npm install --prefix /tmp/tower-console-qa --no-audit --no-fund jsdom
NODE_PATH=/tmp/tower-console-qa/node_modules node tests/console_ui.cjs
```

This is a test-only dependency; serving the packaged console requires no Node.

## Operational safety roadmap

See [planned safety acceptance criteria](ROADMAP.md#operational-safety-coordination-planned) for responsibilities and
dependencies. These additions do not claim implemented end-to-end containment
or integrity protection.

### Sidecar v0.7 evidence compatibility

Native decision summaries retain decision IDs, trigger details and approval/plan
causal links from Sidecar runtime journals. All seven governance outcomes remain
separate from fleet health. See
[the journal readback example](examples/inspect_sidecar_journal.py) and
[compatibility scope](docs/ecosystem-alignment.md#sidecar-v07-runtime-journal-readback).
Sidecar's local Control Room owns task controls; this does not add remote
operator writes to Tower or require a sibling package.

## Sidecar 0.8 interoperability

Tower 0.5.1 retains its existing native Decision/journal readers and separate
deployment-health model. Sidecar 0.8 adds mandatory-scope fingerprints and
correlated evidence without changing Decision status semantics. Shared/Exclusive
context must not be copied into fleet views without reader authorization.

Sidecar 0.8 provides Shared/Exclusive context-only, guardrails-only or combined
configuration, explicit host context delivery and mandatory guardrail composition.
Exclusive rules cannot weaken shared restrictions. Cross-framework privacy,
revocation and delegated authority remain v0.9 validation; stable schemas remain
v1.0. Native correlated Lens readback requires Lens 0.7.1. All sibling packages
stay optional; no dependency floor is increased without a runtime requirement.
See the [Sidecar integration contract](https://github.com/DeepAgentLabs/agentic-sidecar/blob/main/docs/integrations.md).

## Native Evals contract validation — Control Tower 0.6.1

Published Evals 0.7.2 report and gate schemas are now enforced in the native
consumer paths. Validation runs offline using bundled upstream contracts;
invalid artifacts fail with field-level diagnostics. Native verdicts and
AIOS conformance remain distinct. See [behavior, examples and migration](docs/evals-report-contract.md).

Agentic Evals 0.7.2 publishes native report (`schema_version: "1.0"`) and
gate-decision JSON Schemas, with offline `report_schema()` and
`gate_decision_schema()` accessors. Contract 1.x evolves additively; readers
should tolerate unknown fields. Tower continues to read native report/gate fields and display the producer verdict. Schema validation does not recompute a gate or establish evidence integrity.

See the [contract, examples and compatibility policy](https://github.com/DeepAgentLabs/agentic-evals/blob/main/docs/report-contract.md). Existing dependency
ranges remain sufficient; using the new accessors directly requires
`agentic-evals>=0.7.2`. This documentation alignment needs no sibling patch release.

## AgenticLens 0.8.0 suite management

AgenticLens 0.8.0 delivers its v0.6 milestone: `agenticlens.suites` and
`agenticlens suite` build regression suites from CSV/JSON imports, production
traces and user feedback. It masks PII by default before storage (`--no-mask`
opts out), detects duplicates and
conflicting labels, adds synthetic variations and stable splits, records
reviews, and approves suites into immutable, hash-verified versions that CI
verifies, exports and evaluates. Suites stay plain agentic-evals `TestSuite`
files.

Tower's native readers are unchanged. Lens 0.8.0 is inside Tower's
`agenticlens>=0.7,<1` extra. Approved suite versions are Lens-local
artifacts, not Tower evidence types; evaluation reports produced from them
keep the native shape Tower already reads. No Tower release is needed.

See the [suite management guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.8.0/docs/suite-management.md).

## Evals 0.8.0 CLI interoperability

Evals 0.8.0 CLI JSON reports and gate decisions retain schema 1.0 and work with the native Evals evidence reader and bundled 0.7.2 schemas. Keep JSON artifacts when producing JUnit or Markdown for CI; presentation output is not a Tower evidence input. Gate results remain producer evidence, separate from deployment health and recovery authorization.

See [CLI usage and compatibility](docs/evals-0.8-cli.md).

## Chaos 0.7.0 interoperability

Chaos 0.7.0 adds sequential fault cascades, deterministic monotonic breaking-point
search, synthetic response poisoning (including prompt/tool-response instruction
and policy-bypass payloads), and explicit-price retry cost estimates. Native
child event IDs and fault types remain intact; cascade IDs/stages and poisoning
strategy/payload/seed are additive event detail. Existing report readers and
AIOS exports remain compatible.

See the [v0.7 guide and offline synthetic example](https://github.com/DeepAgentLabs/agentic-chaos/blob/v0.7.0/docs/v0.7.md).
The example includes observed synthetic dispatches and a bypassed negative
control. Injection or recovery alone does not prove containment. No new shared
schema, automatic adapter, hosted execution capability or containment guarantee
is introduced.

Tower summarizes native Chaos event counts; resilience outcomes remain separate from deployment health. Its agentic-chaos>=0.5,<1 extra already admits 0.7. No Tower patch release is needed.

## Fleet operations — 0.7.0

Bulk desired configuration and host-installed Sidecar stop/MCP revocation now
ship through Python, HTTP and CLI. Preview a frozen environment/capability
target list, obtain separate approval, execute once, and inspect durable
per-target results and audit events. Partial failures remain explicit;
there is no fleet atomicity, automatic rollback, or remote configuration claim.
See the [operator guide](docs/fleet-operations.md) and run
`uv run python examples/fleet_operations.py`. New fleet endpoints are not
exposed through MCP; all sibling extras remain optional.
