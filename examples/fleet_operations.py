"""Offline fleet example: one stale target fails without undoing the successful target."""

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.bulk import BulkRequest
from agenticops_control_tower.config import Configuration, Operator
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.models import AgentRegistrationPayload
from agenticops_control_tower.registry import AgentRegistry


def main() -> None:
    api = ControlTowerAPI(AgentRegistry(), CapabilityDiscoveryService())
    writer = Operator(operator_id="operator", role="writer")
    approver = Operator(operator_id="reviewer", role="approver")
    for agent_id in ("staging-b", "staging-a"):
        api.register(
            AgentRegistrationPayload(
                agent_id=agent_id,
                name=agent_id,
                environment="staging",
                runtime="custom",
                framework="custom",
                capabilities={"agenticlens": "0.8.0"},
            )
        )
        api.config.declare(
            Configuration(agent_id=agent_id, capability="agenticlens", authority="tower"), writer
        )
    preview = api.bulk.preview(
        BulkRequest(
            intent="Enable enhanced staging tracing",
            operation="config.update",
            selector={"environment": "staging", "capability": "agenticlens"},
            patch={"values": {"enhanced_tracing": True}},
        ),
        writer,
    )
    api.bulk.decide(preview.bulk_id, True, approver)
    api.config.declare(api.config.get("staging-b", "agenticlens"), writer)
    result = api.bulk.execute(preview.bulk_id, writer)
    assert [(t.agent_id, t.outcome) for t in result.targets] == [
        ("staging-a", "succeeded"),
        ("staging-b", "failed"),
    ]
    assert api.bulk.get(result.bulk_id, writer).status == "completed"
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
