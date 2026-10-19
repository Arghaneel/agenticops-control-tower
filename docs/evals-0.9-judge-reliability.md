# Evals 0.9.0 judge reliability and live resilience (Tower 0.7.1)

Agentic Evals 0.9.0 adds optional fields to native report schema `1.0`. They
record judge cost, retries, unavailable judgments and sampling agreement, and
live-target timeouts and errors per case. Control Tower 0.7.1 bundles the exact
Evals 0.9.0 report and gate schemas and validates complete reports and supplied
gates against them before projecting evidence, as before.

Evidence details for an `agentic-evals` evaluation report now also carry:

| Projected field | Source | Meaning |
| --- | --- | --- |
| `summary.judge.judge_scores`, `unavailable_scores`, `unavailable_cases` | `summary.judge` | judgments made, and those the judge could not deliver |
| `summary.judge.total_cost_usd`, `min_agreement` | `summary.judge` | judge spend (null unless every judge score was priced) and the lowest sampling agreement |
| `summary.live.retried_cases`, `timed_out_cases`, `error_cases` and their case IDs | `summary.live` | target outages, kept apart from wrong answers |

Both are `null` in reports written before Evals 0.9.0. `summary.live` is
also `null` for offline (non-live) evaluations, and `summary.judge` is `null`
when a report has no judge scores; an offline evaluation with LLM judges does
carry `summary.judge`, and Tower projects it. Tower shows a missing summary as
missing, not as healthy.

The producer's gate stays authoritative. Evals 0.9.0 fails its default gate when
any judgment is unavailable, and Tower carries `gate.passed` and `reasons`
unchanged without recomputing them. An unavailable judge, a timed-out case or a
passing gate is evaluation evidence. None of them is deployment health,
recovery authorization or proof of containment.

The base package still imports no sibling. The optional `agentic-evals` extra
keeps `>=0.7.2,<1`; only the contract-test dev pin moves to `0.9.0`. See the
[Evals guide](https://github.com/DeepAgentLabs/agentic-evals/blob/v0.9.0/docs/judge-reliability.md).
