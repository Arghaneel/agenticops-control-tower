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

The docs (`docs/`), the use cases (`usecases/`) and the product page
(`index.html`, `site.css`, `site.js`, `og.png`) are built and published together
by `.github/workflows/docs.yml`.

```bash
uv sync --extra docs
uv run mkdocs serve                                  # docs at http://127.0.0.1:8000/
uv run mkdocs build --strict --site-dir site/docs    # what CI runs
uv run mkdocs build --strict -f mkdocs.usecases.yml --site-dir site/usecases
python -m http.server 8000                           # product page, from the repo root
```

Every page must be listed in `nav`; the strict build fails otherwise. Use
relative links in the product page (`href="docs/"`, never `/docs/`), because the
site is served from `deepagentlabs.io/agenticops-control-tower/`.

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
