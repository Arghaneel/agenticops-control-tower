# MCP 0.4.0 unified workflows

[MCP 0.4.0](https://github.com/DeepAgentLabs/mcp-server/releases/tag/v0.4.0) ships the first Phase 4 unified workflows: `core.compare_runs`, a fail-closed `core.release_check`, `core.incident_summary` and `core.export_report`. MCP judges nothing itself; it composes Lens comparisons, the Evals release gate and Chaos run reports. Malformed or failed-call evidence always blocks readiness, and so does missing evidence of a required kind; all three kinds are required by default and `required_evidence` narrows that.

## Connector

- `deep-agentic-core-mcp` 0.4.0 satisfies Tower's `>=0.3.6,<1` range.
- The `tower.*` tools and the `tower.investigation` prompt are unchanged and
  local stdio only; hosted MCP still rejects them.

## Unified workflows

- `core.incident_summary` is an MCP session view of failure signals, not a Tower
  incident, and does not call Tower.
- `core.export_report` returns an MCP-local `mcp.unified-report.v1` envelope that
  Tower does not ingest.

## Compatibility

No Tower API change, dependency bump or release.

See the [MCP unified workflows guide](https://github.com/DeepAgentLabs/mcp-server/blob/v0.4.0/docs/unified-workflows.md).
