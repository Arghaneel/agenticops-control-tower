# Pre-Release Checklist

Current target: `v0.5.0`. Keep this checklist aligned with the current API and
release procedure in [AGENTS.md](AGENTS.md#release).

## Scope and metadata

- Match `pyproject.toml`, `src/agenticops_control_tower/__init__.py` and `uv.lock`.
- Use a plain `## 0.5.0` changelog heading with the release date in its body.
- Align README/roadmap with implemented registry, SQLite persistence,
  authenticated API/CLI, controlled configuration approvals, evidence posture and
  read-only console. Evidence posture preserves producer outcomes independently
  of fleet health.
- Pull-based remote collection and operator remediation remain planned. Siblings
  remain optional; this release requires no sibling package for Tower startup.

## Validation

```bash
make check
make test-ecosystem-published
NODE_PATH=/tmp/tower-console-qa/node_modules node tests/console_ui.cjs
uv run python -m build --outdir /tmp/tower-0.5.0-dist
uv run twine check /tmp/tower-0.5.0-dist/*
# Install and test the built wheel outside the editable checkout.
tower_checkout="$PWD"
tower_smoke_dir="$(mktemp -d)"
uv venv "$tower_smoke_dir/venv"
uv pip install --python "$tower_smoke_dir/venv/bin/python" "/tmp/tower-0.5.0-dist/agenticops_control_tower-0.5.0-py3-none-any.whl[api]"
cd "$tower_smoke_dir"
"$tower_smoke_dir/venv/bin/agenticops-control-tower" --help
"$tower_smoke_dir/venv/bin/agenticops-control-tower" --snapshot "$tower_checkout/examples/sample_fleet_snapshot.json" agents list
"$tower_smoke_dir/venv/bin/agenticops-control-tower" --snapshot "$tower_checkout/examples/sample_fleet_snapshot.json" capabilities list
"$tower_smoke_dir/venv/bin/agenticops-control-tower" --snapshot "$tower_checkout/examples/sample_fleet_snapshot.json" status
"$tower_smoke_dir/venv/bin/agenticops-control-tower" --snapshot "$tower_checkout/examples/sample_fleet_snapshot.json" posture
"$tower_smoke_dir/venv/bin/python" - <<'PY'
from importlib.resources import files
from agenticops_control_tower import __version__
from agenticops_control_tower.adapters import summarize_evidence
from agenticops_control_tower.models.evidence import EvidenceLink
assert __version__ == "0.5.0"
assert files("agenticops_control_tower.console").joinpath("static/index.html").is_file()
link = EvidenceLink(agent_id="smoke", source="agentic-sidecar", source_version="0.7.0",
                    artifact_type="decision", artifact_ref="decision:smoke",
                    observed_at="2026-10-12T00:00:00Z")
result = summarize_evidence(link, {"decision_id": "smoke", "status": "PAUSE",
                                   "risk": "HIGH", "reason": "release smoke"})
assert result.availability == "available"
assert result.details["decision_id"] == "smoke"
from agenticops_control_tower.evidence import EvidenceStore, PostureService
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.registry import AgentRegistry
registry = AgentRegistry()
registry.register(AgentRegistrationPayload(agent_id="smoke", name="smoke", environment="test",
                                           runtime="custom", framework="custom"))
store = EvidenceStore(registry)
store.ingest(EvidenceIngestRequest(link=link, artifact={"status": "PAUSE", "risk": None,
                                                         "reason": "release smoke"}))
posture = PostureService(store).agent(registry.get("smoke"), now=link.observed_at)
assert {s.source: s.freshness for s in posture.sources}["agentic-sidecar"] == "fresh"
PY
cd "$tower_checkout"
```

Verify wheel/sdist name and version metadata, installed entry point, and packaged
console assets. The CLI/API need the optional `api` extra; base Python evidence
readers and the evidence store remain standalone. Missing optional producer tests
skip honestly; `make test-ecosystem-published` runs them against the published
sibling extras.

## Tag and publish

Prepare version/changelog changes on a branch, merge the reviewed PR, then tag
that merge commit. Extract the matching changelog section into a temporary file:

```bash
uv run python - <<'PY'
from pathlib import Path
text = Path("CHANGELOG.md").read_text()
section = text.split("## 0.5.0\n", 1)[1].split("\n## ", 1)[0].strip()
Path("/tmp/tower-0.5.0-release-notes.md").write_text(section + "\n")
PY
git tag -a v0.5.0 -F /tmp/tower-0.5.0-release-notes.md --cleanup=verbatim
git push origin v0.5.0
```

The release workflow builds artifacts, publishes to PyPI through Trusted
Publishing and creates the GitHub release using the same changelog section.
Do not manually create a second release or publish unrelated tags.

## Post-publication

- Confirm publishing and GitHub release jobs succeeded.
- Verify both wheel and source distribution on PyPI.
- Install `agenticops-control-tower[api]==0.5.0` in a fresh environment and smoke
  the CLI/offline snapshot posture, native evidence reader and evidence store.
