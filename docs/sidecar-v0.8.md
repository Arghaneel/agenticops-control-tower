# Sidecar 0.8 integration boundary

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
