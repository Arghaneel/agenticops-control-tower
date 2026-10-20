"""Offline native-JSON live detection demo; no sibling packages or network required."""

import json
from datetime import datetime, timezone

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.config.models import Operator
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
from agenticops_control_tower.registry import AgentRegistry


def walkthrough():
    api = ControlTowerAPI(AgentRegistry(), CapabilityDiscoveryService())
    api.register(AgentRegistrationPayload(agent_id="demo", name="Demo", environment="staging",
                 runtime="custom", framework="custom", status="healthy"))
    api.ingest_evidence(EvidenceIngestRequest.model_validate(dict(
        link=dict(agent_id="demo", source="agenticlens", source_version="0.10.0",
                  artifact_type="run", artifact_ref="run:demo", run_id="demo-run",
                  observed_at=datetime.now(timezone.utc).isoformat()),
        artifact=dict(schema_version="1.0", run_id="demo-run", application_name="demo",
                      status="failed", task_success=False, spans=[]))))
    operator = Operator(operator_id="demo-operator", role="writer")
    alert = api.operations.evaluate(operator)[0]
    assert len(api.operations.evaluate(operator)) == 1
    api.operations.acknowledge(alert.alert_id, operator)
    view = api.operations.incident_view(alert.incident_id, operator)
    assert view["agent"].status == "healthy"
    assert view["incident"].state == "open"
    return dict(rule=alert.rule, alerts=len(api.operations.list(operator)),
                reported_health=view["agent"].status, state=view["incident"].state,
                lens_integrity=view["lens_integrity"],
                events=[e["event"] for e in view["timeline"]])


if __name__ == "__main__":
    print(json.dumps(walkthrough(), indent=2))
