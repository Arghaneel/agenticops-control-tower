# Pre-Release Checklist

Current target: `v0.3.1`. Keep this checklist aligned with the current API and
release procedure in [AGENTS.md](AGENTS.md#release).

## Scope and metadata

- Match `pyproject.toml`, `src/agenticops_control_tower/__init__.py` and `uv.lock`.
- Use a plain `## 0.3.1` changelog heading with the release date in its body.
- Align README/roadmap with implemented registry, SQLite persistence,
  authenticated API/CLI and read-only console. Native evidence readers preserve
  producer outcomes independently of fleet health.
- Remote event collection and operator remediation remain planned. Sidecar
  remains optional; this patch requires no sibling package for Tower startup.

## Validation

```bash
make check
uv run --with agentic-sidecar==0.7.0 python -m pytest tests/test_sibling_artifacts.py -k sidecar
uv run python -m build --outdir /tmp/tower-0.3.1-dist
uv run twine check /tmp/tower-0.3.1-dist/*
uv run agenticops-control-tower --help
uv run agenticops-control-tower --snapshot examples/sample_fleet_snapshot.json agents list
uv run agenticops-control-tower --snapshot examples/sample_fleet_snapshot.json capabilities list
uv run agenticops-control-tower --snapshot examples/sample_fleet_snapshot.json status
```

Verify wheel/sdist name and version metadata, installed entry point, and packaged
console assets. The CLI/API need the optional `api` extra; base Python evidence
readers remain standalone. Missing optional producer tests skip honestly; run
Sidecar checks explicitly against its published package.

## Tag and publish

Prepare version/changelog changes on a branch, merge the reviewed PR, then tag
that merge commit. Extract the matching changelog section into a temporary file:

```bash
git tag -a v0.3.1 -F /tmp/tower-0.3.1-release-notes.md --cleanup=verbatim
git push origin v0.3.1
```

The release workflow builds artifacts, publishes to PyPI through Trusted
Publishing and creates the GitHub release using the same changelog section.
Do not manually create a second release or publish unrelated tags.

## Post-publication

- Confirm publishing and GitHub release jobs succeeded.
- Verify both wheel and source distribution on PyPI.
- Install `agenticops-control-tower[api]==0.3.1` in a fresh environment and smoke
  the CLI/offline snapshot and native evidence reader.
