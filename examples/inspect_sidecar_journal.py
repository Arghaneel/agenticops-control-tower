"""Read native Sidecar decision evidence from a JSONL journal or demo recording."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from agenticops_control_tower.models import AgentRegistrationPayload
from agenticops_control_tower.models.evidence import EvidenceLink
from agenticops_control_tower.snapshot import create_api


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--agent-id", default="demo-deployment")
    args = parser.parse_args()
    content = args.path.read_text()
    try:
        recording = json.loads(content)
    except json.JSONDecodeError:
        events = [json.loads(line) for line in content.splitlines() if line.strip()]
    else:
        events = recording if isinstance(recording, list) else recording.get("events", [recording])
    api = create_api()
    api.register_agent(
        AgentRegistrationPayload(
            agent_id=args.agent_id,
            name="Local evidence example",
            environment="test",
            runtime="custom",
            framework="custom",
            status="healthy",
        )
    )
    for event in events:
        if event["kind"] != "decision":
            continue
        artifact = event["payload"]["decision"]
        link = EvidenceLink(
            agent_id=args.agent_id,
            source="agentic-sidecar",
            source_version=args.source_version,
            artifact_type="decision",
            artifact_ref="decision:" + artifact["decision_id"],
            observed_at=datetime.fromisoformat(event["timestamp"]),
        )
        print(api.summarize_evidence(link, artifact).model_dump_json(indent=2))
    print(f"Healthy deployments: {api.get_status().healthy_agents}")


if __name__ == "__main__":
    main()
