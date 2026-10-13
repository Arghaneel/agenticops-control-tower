"""Push native producer evidence and read posture with the Python API.

Run from the checkout: uv run python examples/push_ecosystem_evidence.py
Over HTTP, use `agenticops-control-tower evidence ingest-manifest
examples/evidence/manifest.json` with a writer token instead.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.snapshot import create_api

directory = Path(__file__).parent / "evidence"
manifest = json.loads((directory / "manifest.json").read_text())

api = create_api()
api.register(
    AgentRegistrationPayload(
        agent_id="payment-agent",
        name="Payments",
        environment="production",
        runtime="aws-lambda",
        framework="langgraph",
        status="healthy",
    )
)
for entry in manifest["entries"]:
    request = EvidenceIngestRequest(
        link=entry["link"],
        artifact=json.loads((directory / entry["artifact_path"]).read_text()),
        gate=json.loads((directory / entry["gate_path"]).read_text())
        if "gate_path" in entry
        else None,
    )
    result = api.ingest_evidence(request, ingested_by="example")
    print(f"{request.link.source}: {result.record.summary.availability}")

# The sample evidence is dated; evaluate it as of its capture time. Live
# deployments omit `now`, and evidence older than one day is reported stale.
captured_at = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
posture = api.agent_posture("payment-agent", now=captured_at)
for source in posture.sources:
    print(source.source, source.freshness, json.dumps(source.summary))
# Producer outcomes (a failed run, a failed gate, an escalation) never change reported health.
assert api.get_status().healthy_agents == 1
