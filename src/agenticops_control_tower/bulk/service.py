"""Frozen targets and transactionally claimed per-target work, without fleet atomicity."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from queue import Empty, Queue
from threading import BoundedSemaphore, Thread
from uuid import uuid4

from agenticops_control_tower.adapters.containment import SidecarContainmentAdapter
from agenticops_control_tower.bulk.models import BulkAction, BulkEvent, BulkRequest, TargetResult
from agenticops_control_tower.config.models import ActionRequest, ConfigScope, Operator
from agenticops_control_tower.config.service import ConfigurationError, ConfigurationService
from agenticops_control_tower.errors import AgentNotFoundError

_DISPATCH_SLOTS = BoundedSemaphore(16)


def now() -> datetime:
    return datetime.now(timezone.utc)


class BulkService:
    """Use the configuration service's database and transaction lock.

    Runtime connectors are installed by the trusted host for explicit deployment IDs.
    Caller payloads cannot supply endpoints, credentials, commands or connectors.
    """

    def __init__(self, config: ConfigurationService) -> None:
        self.config = config
        self._connectors: dict[str, SidecarContainmentAdapter] = {}
        with config._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tower_bulk (id TEXT PRIMARY KEY, body TEXT)")

    def install(self, agent_id: str, adapter: SidecarContainmentAdapter) -> None:
        self.config.registry.get(agent_id)
        self._connectors[agent_id] = adapter

    @staticmethod
    def _save(db: sqlite3.Connection, action: BulkAction) -> None:
        db.execute(
            "INSERT OR REPLACE INTO tower_bulk VALUES (?, ?)",
            (action.bulk_id, action.model_dump_json()),
        )

    @staticmethod
    def _load(db: sqlite3.Connection, bulk_id: str) -> BulkAction:
        row = db.execute("SELECT body FROM tower_bulk WHERE id=?", (bulk_id,)).fetchone()
        if row is None:
            raise ConfigurationError("Unknown bulk action")
        return BulkAction.model_validate_json(row[0])

    @staticmethod
    def _scope(action: BulkAction, operator: Operator, role: str | None = None) -> None:
        if role is not None and operator.role != role:
            raise ConfigurationError("Operator role does not authorize bulk action")
        if operator.agent_ids is not None and any(
            item.agent_id not in operator.agent_ids for item in action.targets
        ):
            raise ConfigurationError("Operator scope does not include every frozen target")

    @staticmethod
    def _event(
        action: BulkAction, event: str, operator: Operator, agent_id: str | None = None
    ) -> None:
        action.events.append(
            BulkEvent(
                event=event, operator_id=operator.operator_id, recorded_at=now(), agent_id=agent_id
            )
        )

    def get(self, bulk_id: str, operator: Operator) -> BulkAction:
        with self.config._transaction(write=False) as db:
            action = self._load(db, bulk_id)
            self._scope(action, operator)
            return action

    def preview(self, request: BulkRequest, operator: Operator) -> BulkAction:
        if operator.role != "writer":
            raise ConfigurationError("Writer role required")
        selector = request.selector
        agents = [
            a
            for a in self.config.registry.list_agents()
            if a.environment == selector.environment
            and selector.capability in a.capabilities
            and (selector.agent_ids is None or a.agent_id in selector.agent_ids)
        ]
        if not agents or len(agents) > 100:
            raise ConfigurationError("Selector must match between 1 and 100 agents")
        if selector.agent_ids is not None and set(selector.agent_ids) != {
            a.agent_id for a in agents
        }:
            raise ConfigurationError("Explicit targets must all match environment and capability")
        action = BulkAction(
            bulk_id=str(uuid4()),
            request=request.model_copy(deep=True),
            proposed_by=operator.operator_id,
            expires_at=now() + timedelta(seconds=request.expires_in_seconds),
            targets=[
                TargetResult(
                    agent_id=a.agent_id,
                    command_id=str(uuid4()),
                    deployment={
                        "runtime": a.runtime,
                        "framework": a.framework,
                        "version": a.capabilities[selector.capability],
                        "registered_at": a.registered_at.isoformat(),
                    },
                )
                for a in sorted(agents, key=lambda a: a.agent_id)
            ],
        )
        self._scope(action, operator, "writer")
        with self.config._transaction() as db:
            for target in action.targets:
                if request.operation != "runtime.stop":
                    target.preview = self.config._preview(
                        db,
                        ActionRequest(
                            target=ConfigScope(
                                agent_id=target.agent_id,
                                environment=selector.environment,
                                capability=selector.capability,
                            ),
                            operation=request.operation,
                            patch=request.patch,
                            expires_in_seconds=request.expires_in_seconds,
                        ),
                        operator,
                    )
                    # Internal single-target actions cannot be separately approved/executed.
                    db.execute("DELETE FROM tower_actions WHERE id=?", (target.preview.action_id,))
                else:
                    target.detail = (
                        "Stop dispatch and request MCP revocation; no restart or rollback"
                    )
            self._event(action, "bulk.previewed", operator)
            self._save(db, action)
        return action

    def decide(self, bulk_id: str, approved: bool, operator: Operator) -> BulkAction:
        with self.config._transaction() as db:
            action = self._load(db, bulk_id)
            self._scope(action, operator, "approver")
            if action.status != "pending" or action.expires_at <= now():
                raise ConfigurationError("Bulk preview is no longer pending or has expired")
            if action.proposed_by == operator.operator_id:
                raise ConfigurationError("Approval requires a different operator")
            action.status = "approved" if approved else "denied"
            action.decided_by = operator.operator_id
            self._event(action, f"bulk.{action.status}", operator)
            self._save(db, action)
            return action

    def revoke(self, bulk_id: str, operator: Operator) -> BulkAction:
        with self.config._transaction() as db:
            action = self._load(db, bulk_id)
            self._scope(action, operator, "approver")
            if action.status not in ("pending", "approved"):
                raise ConfigurationError("Only unclaimed bulk actions can be revoked")
            action.status = "revoked"
            self._event(action, "bulk.revoked", operator)
            self._save(db, action)
            return action

    def execute(self, bulk_id: str, operator: Operator) -> BulkAction:
        with self.config._transaction() as db:
            action = self._load(db, bulk_id)
            self._scope(action, operator, "writer")
            if action.status != "approved" or action.expires_at <= now():
                raise ConfigurationError("Bulk approval missing, expired or already consumed")
            action.status = "executing"
            self._event(action, "bulk.claimed", operator)
            self._save(db, action)
        for index in range(len(action.targets)):
            self._execute_target(bulk_id, index, operator)
        with self.config._transaction() as db:
            action = self._load(db, bulk_id)
            action.status = "completed"
            self._event(action, "bulk.completed", operator)
            self._save(db, action)
            return action

    def _execute_target(self, bulk_id: str, index: int, operator: Operator) -> None:
        with self.config._transaction() as db:
            action = self._load(db, bulk_id)
            target = action.targets[index]
            try:
                agent = self.config.registry.get(target.agent_id)
                if action.expires_at <= now() or (
                    agent.environment != action.request.selector.environment
                    or target.deployment
                    != {
                        "runtime": agent.runtime,
                        "framework": agent.framework,
                        "version": agent.capabilities.get(action.request.selector.capability, ""),
                        "registered_at": agent.registered_at.isoformat(),
                    }
                ):
                    raise ConfigurationError("Frozen target changed scope or approval expired")
                if target.preview is not None:
                    child = target.preview.model_copy(deep=True)
                    child.status, child.approved_by = "approved", action.decided_by
                    self.config._save_action(db, child)
                    self.config._execute(db, child.action_id, operator)
                    target.outcome = "succeeded"
                elif target.agent_id not in self._connectors:
                    target.outcome = "unsupported"
                    target.detail = "No host-installed containment adapter"
                else:
                    target.outcome = "requested"
            except (ConfigurationError, AgentNotFoundError) as exc:
                target.outcome, target.detail = "failed", str(exc)
            if target.preview is not None:
                db.execute("DELETE FROM tower_actions WHERE id=?", (target.preview.action_id,))
            self.config._audit(
                db,
                operator,
                target.agent_id,
                f"bulk.target.{target.outcome}",
                action.bulk_id,
                target.detail,
            )
            self._event(action, f"target.{target.outcome}", operator, target.agent_id)
            self._save(db, action)
        if target.outcome != "requested":
            return
        queue: Queue[dict[str, object]] = Queue(maxsize=1)
        adapter = self._connectors[target.agent_id]

        def dispatch() -> None:
            try:
                queue.put(adapter.control("stop", operator.operator_id))
            except Exception:
                # Do not persist exception text: a connector may include credentials.
                queue.put({"outcome": "failed", "detail": "Connector raised; inspect host logs"})
            finally:
                _DISPATCH_SLOTS.release()

        if not _DISPATCH_SLOTS.acquire(blocking=False):
            queue.put(
                {"outcome": "failed", "detail": "Host dispatch capacity exhausted; no call made"}
            )
        else:
            Thread(target=dispatch, daemon=True).start()
        try:
            receipt = queue.get(timeout=action.request.acknowledgement_seconds)
            outcome = receipt.get("outcome")
            target.outcome = (
                outcome
                if outcome in ("acknowledged", "failed", "unsupported", "incomplete")
                else "unknown"
            )
            target.receipt = receipt
        except Empty:
            target.outcome = "timed_out"
            target.detail = (
                "Acknowledgement deadline elapsed; host call may still complete; do not retry"
            )
        with self.config._transaction() as db:
            action = self._load(db, bulk_id)
            action.targets[index] = target
            if target.preview is not None:
                db.execute("DELETE FROM tower_actions WHERE id=?", (target.preview.action_id,))
            self.config._audit(
                db,
                operator,
                target.agent_id,
                f"bulk.target.{target.outcome}",
                action.bulk_id,
                target.detail,
            )
            self._event(action, f"target.{target.outcome}", operator, target.agent_id)
            self._save(db, action)
