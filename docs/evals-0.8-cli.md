# Evals 0.8.0 CLI interoperability

Evals 0.8.0 CLI JSON reports and gate decisions retain schema 1.0 and work with the native Evals evidence reader and bundled 0.7.2 schemas. Keep JSON artifacts when producing JUnit or Markdown for CI; presentation output is not a Tower evidence input. Gate results remain producer evidence, separate from deployment health and recovery authorization.

```bash
agentic-evals evaluate suite.yaml samples.jsonl --out report.json
agentic-evals gate report.json --config gate.yaml --out gate.json
```

`evaluate`/`live` exit 0 when a report is produced, even if cases fail.
`gate` exits 0 on pass, 1 on failed policy, and 2 on invalid input or usage.
Use Evals 0.8.0 for these commands; see the [CLI guide and CI example](https://github.com/DeepAgentLabs/agentic-evals/blob/v0.8.0/docs/cli.md).

This is compatibility documentation only: no sibling runtime change,
dependency-floor increase or patch release is required.
