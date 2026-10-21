# Contributing

The repository's
[CONTRIBUTING.md](https://github.com/DeepAgentLabs/agenticops-control-tower/blob/main/CONTRIBUTING.md)
and
[AGENTS.md](https://github.com/DeepAgentLabs/agenticops-control-tower/blob/main/AGENTS.md)
are the source of truth. This page collects the commands.

## Development setup

```bash
git clone https://github.com/DeepAgentLabs/agenticops-control-tower.git
cd agenticops-control-tower
make install   # uv sync --extra dev
make check     # lint, format check, mypy --strict, pytest
```

Run `make check` before every push. `make test-ecosystem` runs the optional
sibling-package tests against local checkouts.

## Working on this documentation site

The docs (`docs/`), use cases (`usecases/`) and product page are owned here.
The [main website](https://github.com/DeepAgentLabs/deepagentlabs.github.io)
publishes them at `/control-tower/` using its shared documentation builder.
The repository Docs workflow validates the same output and uploads a preview.
See [publishing](publishing.md) for triggers and the canonical URLs.

From a workspace with this repository and `deepagentlabs.github.io` as siblings:

```bash
uv run --no-project --with-requirements ../deepagentlabs.github.io/scripts/docs-requirements.txt python ../deepagentlabs.github.io/scripts/build_docs.py --project agenticops-control-tower --repo . --output site/docs
uv run --no-project --with-requirements ../deepagentlabs.github.io/scripts/docs-requirements.txt python ../deepagentlabs.github.io/scripts/build_docs.py --project agenticops-control-tower --section usecases --repo . --output site/usecases
python ../deepagentlabs.github.io/scripts/check_docs_site.py site
```

The product page uses relative asset and documentation links so it works at the
canonical product prefix. Keep the screenshots labeled as sample data.

## Accuracy rules

- Document only what the code does today. Planned work goes in the
  [roadmap](roadmap.md).
- Run every command and example before committing it, and state the version it
  was verified against.
- Label each capability **stable** or **experimental**.

## Scope

Control Tower owns operator-facing control-plane behaviour: inventory, status,
configuration, evidence posture and incident coordination. Observability,
evaluation, supervision, chaos and MCP logic belong in the sibling repositories.
