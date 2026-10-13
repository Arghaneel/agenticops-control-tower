"""Snapshot loading helpers for CLI and tests."""

from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path

from pydantic import ValidationError

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.errors import AgenticOpsControlTowerError, SnapshotLoadError
from agenticops_control_tower.models import (
    AgentRegistrationPayload,
    FleetSnapshot,
    HeartbeatPayload,
)
from agenticops_control_tower.registry import AgentRegistry
from agenticops_control_tower.status import StatusService


def create_api() -> ControlTowerAPI:
    """Create an empty control-plane API using the shared v0.2 services."""

    discovery = CapabilityDiscoveryService()
    return ControlTowerAPI(
        registry=AgentRegistry(),
        discovery=discovery,
        status_service=StatusService(discovery),
    )


def read_snapshot(snapshot_path: str | Path) -> FleetSnapshot:
    """Parse and validate a snapshot artifact without building an API."""

    snapshot_file = Path(snapshot_path)
    try:
        snapshot = FleetSnapshot.model_validate(json.loads(snapshot_file.read_text()))
    except OSError as exc:
        raise SnapshotLoadError(str(snapshot_file), str(exc)) from exc
    except JSONDecodeError as exc:
        raise SnapshotLoadError(str(snapshot_file), f"invalid JSON at line {exc.lineno}") from exc
    except ValidationError as exc:
        raise SnapshotLoadError(str(snapshot_file), exc.errors()[0]["msg"]) from exc
    return snapshot


def load_snapshot(snapshot_path: str | Path) -> ControlTowerAPI:
    """Build an in-memory control-plane API from a snapshot artifact.

    Snapshot evidence is ingested as of `captured_at`; evaluate its posture with
    `now=snapshot.captured_at` so offline freshness does not drift with wall time.
    """

    snapshot = read_snapshot(snapshot_path)
    api = create_api()
    for registration in snapshot.registrations:
        api.register_agent(
            AgentRegistrationPayload(
                agent_id=registration.agent_id,
                name=registration.name,
                environment=registration.environment,
                runtime=registration.runtime,
                framework=registration.framework,
                status=registration.status,
                capabilities=registration.capabilities,
                runtime_metadata=registration.runtime_metadata,
                package_metadata=registration.package_metadata,
                registered_at=registration.registered_at or snapshot.captured_at,
            )
        )
    for event in snapshot.heartbeats:
        api.record_heartbeat(
            event.agent_id,
            HeartbeatPayload(
                status=event.heartbeat.status,
                last_seen=event.heartbeat.last_seen or snapshot.captured_at,
                capabilities=event.heartbeat.capabilities,
                runtime_metadata=event.heartbeat.runtime_metadata,
                package_metadata=event.heartbeat.package_metadata,
            ),
        )
    for request in snapshot.evidence:
        try:
            api.evidence.ingest(request, ingested_by="snapshot", now=snapshot.captured_at)
        except AgenticOpsControlTowerError as exc:
            raise SnapshotLoadError(str(snapshot_path), str(exc)) from exc
    return api
