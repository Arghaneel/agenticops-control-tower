# Tower 0.8.0 ecosystem compatibility

Tower 0.8.0 adds periodic local telemetry detection, durable deduplicated alerts,
acknowledgements and read-only incident console views. Existing native evidence,
recovery approval and fleet-operation contracts remain compatible.

| Component | Compatibility and ownership |
| --- | --- |
| AgenticLens 0.10.0 | Native runs remain inputs; fresh failed runs can create incidents. Integrity/coverage stay explicitly unverified/unassessed. Routing and ModelFit artifacts are not automatic detection inputs. |
| Agentic Evals 0.9.0 | Bundled report/gate schemas remain unchanged; Tower does not recompute scoring or gates. Recovery still requires passing same-run evidence. |
| Agentic Sidecar 0.9.0 | Explicit same-run native decisions join incident evidence. Scope enforcement, private context and dispatch blocking remain Sidecar-owned. |
| Agentic Chaos 0.8.0 | Existing report projections and posture remain valid. Chaos workflow status is not deployment health or automatic remediation authority. |
| MCP 0.4.1 | Existing local authenticated `tower.*` tools remain compatible. Alert/view endpoints are accessed through Tower API/CLI, not new MCP tools. Hosted credentials remain separate work. |
| AI Operations Specification v0.6 | No normative schema changes; Tower-local alerts, incident links and correlation keys do not establish AIOS conformance. |

No new sibling runtime calls or dependency floors are needed. All producers are
optional, and documentation-only compatibility updates need no sibling patch
release. Run `make test-ecosystem-published` and `make test-ecosystem` to verify
native producer boundaries. See [operator workflow](live-operations.md).
