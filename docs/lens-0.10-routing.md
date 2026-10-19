# Lens routing integration boundary

## AgenticLens 0.10.0 routing compatibility

AgenticLens 0.10.0 implements roadmap v0.8: evidence-based runtime model
selection, fail-closed routing constraints, bounded provider failover,
confidence/escalation handoffs, shadow/canary modes and a local routing journal.
The default is advisory; execution uses explicit caller-owned callbacks.
MCP 0.3.12 exposes read-only `lens.routing_decide` and pins hosted Lens 0.10.0.
See the [routing guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.10.0/docs/routing.md)
and [offline example](https://github.com/DeepAgentLabs/agenticlens/blob/v0.10.0/examples/routing_demo.py).

Fleet inventory, desired host settings, authenticated approval and native producer
evidence remain Tower-owned. Routing decisions are Lens-local artifacts; no new
automatic Tower reader or native posture tally is introduced. Route selection
is not deployment health or a Tower approval. Existing optional ranges remain
sufficient; no Tower patch release is required.
