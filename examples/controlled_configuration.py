"""Run from the checkout: uv run python examples/controlled_configuration.py."""

from agenticops_control_tower.config import (
    ActionRequest,
    Configuration,
    ConfigurationService,
    Operator,
)
from agenticops_control_tower.models import AgentRegistrationPayload
from agenticops_control_tower.registry import AgentRegistry

registry = AgentRegistry()
registry.register(
    AgentRegistrationPayload(
        agent_id="example",
        name="Example",
        environment="staging",
        runtime="custom",
        framework="custom",
    )
)
service = ConfigurationService(registry)
writer = Operator(operator_id="alice", role="writer", agent_ids=["example"])
approver = Operator(operator_id="bob", role="approver", agent_ids=["example"])
service.declare(
    Configuration(
        agent_id="example",
        capability="routing",
        authority="tower",
        reason="Tower desired routing policy",
    ),
    writer,
)
request = ActionRequest(
    target={"agent_id": "example", "capability": "routing", "environment": "staging"},
    operation="config.update",
    patch={"values": {"preferred_region": "us-east"}},
)
preview = service.preview(request, writer)
print(preview.model_dump_json(indent=2))
service.approve(preview.action_id, True, approver)
print(service.execute(preview.action_id, writer).model_dump_json(indent=2))
