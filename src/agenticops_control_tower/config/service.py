"""Transactional desired configuration, approvals and audit storage.

Tower-owned desired settings never imply a remote runtime change. SQLite
transactions serialize approvals and executions across server processes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import RLock
from typing import ParamSpec, TypeVar
from uuid import uuid4

from agenticops_control_tower.config.models import (
    ActionPreview,
    ActionRequest,
    AuditRecord,
    Configuration,
    ExecutionResult,
    Operator,
)
from agenticops_control_tower.registry import AgentRegistry


class ConfigurationError(ValueError):
    """An action is unsupported, unauthorized, stale, or no longer approved."""


P = ParamSpec("P")
T = TypeVar("T")


def audited(method: Callable[P, T]) -> Callable[P, T]:
    """Record rejected commands after their mutation transaction rolls back."""

    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return method(*args, **kwargs)
        except ConfigurationError:
            service = args[0]
            if isinstance(service, ConfigurationService):
                operator = next(
                    (item for item in (*args, *kwargs.values()) if isinstance(item, Operator)), None
                )
                target = args[1] if len(args) > 1 else None
                agent_id = ""
                action_id = None
                if isinstance(target, ActionRequest):
                    agent_id = target.target.agent_id
                elif isinstance(target, Configuration):
                    agent_id = target.agent_id
                elif isinstance(target, str):
                    try:
                        action = service.action(target)
                        agent_id = action.request.target.agent_id
                        action_id = target
                    except ConfigurationError:
                        pass
                if operator and agent_id:
                    with service._transaction() as db:
                        service._audit(
                            db,
                            operator,
                            agent_id,
                            "action.rejected",
                            action_id,
                            "Authorization or action precondition rejected",
                        )
            raise

    return wrapped


class ConfigurationService:
    def __init__(self, registry: AgentRegistry, database_path: str | None = None) -> None:
        self.registry = registry
        self._lock = RLock()
        self._memory = sqlite3.connect(":memory:", check_same_thread=False)
        self._path = database_path
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tower_config (id TEXT PRIMARY KEY, body TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS tower_actions (id TEXT PRIMARY KEY, body TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS tower_audit (id INTEGER PRIMARY KEY, body TEXT)")

    @contextmanager
    def _transaction(self, *, write: bool = True) -> Iterator[sqlite3.Connection]:
        with self._lock:
            db = sqlite3.connect(self._path) if self._path else self._memory
            try:
                db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                if self._path:
                    db.close()

    @staticmethod
    def _key(agent_id: str, capability: str) -> str:
        return f"{agent_id}:{capability}"

    def _get(self, db: sqlite3.Connection, agent_id: str, capability: str) -> Configuration:
        self.registry.get(agent_id)
        row = db.execute(
            "SELECT body FROM tower_config WHERE id=?", (self._key(agent_id, capability),)
        ).fetchone()
        if row:
            return Configuration.model_validate_json(row[0])
        return Configuration(agent_id=agent_id, capability=capability)

    def get(self, agent_id: str, capability: str) -> Configuration:
        with self._transaction(write=False) as db:
            return self._get(db, agent_id, capability)

    @staticmethod
    def _authorize(operator: Operator, agent_id: str, role: str) -> None:
        if operator.role != role or (
            operator.agent_ids is not None and agent_id not in operator.agent_ids
        ):
            raise ConfigurationError("Operator role or deployment scope does not authorize action")

    @staticmethod
    def _audit(
        db: sqlite3.Connection,
        operator: Operator,
        agent_id: str,
        event: str,
        action_id: str | None = None,
        detail: str = "",
    ) -> None:
        record = AuditRecord(
            event_id=str(uuid4()),
            action_id=action_id,
            operator_id=operator.operator_id,
            agent_id=agent_id,
            event=event,
            detail=detail,
            recorded_at=datetime.now(timezone.utc),
        )
        db.execute("INSERT INTO tower_audit(body) VALUES (?)", (record.model_dump_json(),))

    @audited
    def declare(self, configuration: Configuration, operator: Operator) -> Configuration:
        """Trusted Python setup declares ownership; HTTP cannot elevate a mirror."""
        self._authorize(operator, configuration.agent_id, "writer")
        with self._transaction() as db:
            previous = self._get(db, configuration.agent_id, configuration.capability)
            result = configuration.model_copy(update={"revision": previous.revision + 1}, deep=True)
            db.execute(
                "INSERT OR REPLACE INTO tower_config VALUES (?, ?)",
                (
                    self._key(result.agent_id, result.capability),
                    result.model_dump_json(),
                ),
            )
            self._audit(db, operator, result.agent_id, "configuration.declared")
            return result

    @audited
    def preview(self, request: ActionRequest, operator: Operator) -> ActionPreview:
        agent_id = request.target.agent_id
        self._authorize(operator, agent_id, "writer")
        capability = request.target.capability
        if not capability:
            raise ConfigurationError("An explicit capability target is required")
        with self._transaction() as db:
            return self._preview(db, request, operator)

    def _preview(
        self, db: sqlite3.Connection, request: ActionRequest, operator: Operator
    ) -> ActionPreview:
        agent_id = request.target.agent_id
        capability = request.target.capability
        agent = self.registry.get(agent_id)
        if (
            request.target.environment is not None
            and request.target.environment != agent.environment
        ):
            raise ConfigurationError("Target environment does not match deployment")
        before = self._get(db, agent_id, capability)
        if before.authority != "tower":
            raise ConfigurationError(before.reason)
        after = before.model_copy(deep=True)
        if request.operation == "config.update":
            after.values.update(request.patch.values)
        else:
            if request.patch.values:
                raise ConfigurationError("Capability toggles do not accept a configuration patch")
            after.enabled = request.operation == "capabilities.enable"
        after.revision += 1
        action = ActionPreview(
            action_id=str(uuid4()),
            request=request.model_copy(deep=True),
            proposed_by=operator.operator_id,
            expected_revision=before.revision,
            before=before,
            after=after,
            impact="Changes Tower-owned desired configuration only; no remote execution",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=request.expires_in_seconds),
        )
        self._save_action(db, action)
        self._audit(db, operator, agent_id, "action.previewed", action.action_id)
        return action

    @staticmethod
    def _save_action(db: sqlite3.Connection, action: ActionPreview) -> None:
        db.execute(
            "INSERT OR REPLACE INTO tower_actions VALUES (?, ?)",
            (
                action.action_id,
                action.model_dump_json(),
            ),
        )

    @staticmethod
    def _action(db: sqlite3.Connection, action_id: str) -> ActionPreview:
        row = db.execute("SELECT body FROM tower_actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise ConfigurationError("Unknown action")
        return ActionPreview.model_validate_json(row[0])

    def action(self, action_id: str) -> ActionPreview:
        with self._transaction(write=False) as db:
            return self._action(db, action_id)

    @audited
    def approve(self, action_id: str, approved: bool, operator: Operator) -> ActionPreview:
        with self._transaction() as db:
            action = self._action(db, action_id)
            self._authorize(operator, action.request.target.agent_id, "approver")
            if action.status != "pending" or action.expires_at <= datetime.now(timezone.utc):
                raise ConfigurationError("Action is no longer pending or has expired")
            if operator.operator_id == action.proposed_by:
                raise ConfigurationError("Approval requires a different operator")
            action.status = "approved" if approved else "denied"
            action.approved_by = operator.operator_id if approved else None
            action.decided_by = operator.operator_id
            self._save_action(db, action)
            self._audit(
                db, operator, action.request.target.agent_id, f"action.{action.status}", action_id
            )
            return action

    @audited
    def revoke(self, action_id: str, operator: Operator) -> ActionPreview:
        with self._transaction() as db:
            action = self._action(db, action_id)
            self._authorize(operator, action.request.target.agent_id, "approver")
            if action.status not in ("pending", "approved"):
                raise ConfigurationError("Action cannot be revoked in its current state")
            action.status = "revoked"
            self._save_action(db, action)
            self._audit(db, operator, action.request.target.agent_id, "action.revoked", action_id)
            return action

    @audited
    def execute(self, action_id: str, operator: Operator) -> ExecutionResult:
        with self._transaction() as db:
            return self._execute(db, action_id, operator)

    def _execute(
        self, db: sqlite3.Connection, action_id: str, operator: Operator
    ) -> ExecutionResult:
        action = self._action(db, action_id)
        target = action.request.target
        self._authorize(operator, target.agent_id, "writer")
        if action.status != "approved" or action.expires_at <= datetime.now(timezone.utc):
            raise ConfigurationError("Approval is missing, denied, revoked, consumed or expired")
        current = self._get(db, target.agent_id, action.after.capability)
        agent = self.registry.get(target.agent_id)
        if (
            current != action.before
            or current.revision != action.expected_revision
            or (target.environment is not None and target.environment != agent.environment)
        ):
            raise ConfigurationError("Approval no longer matches current configuration or target")
        db.execute(
            "INSERT OR REPLACE INTO tower_config VALUES (?, ?)",
            (
                self._key(target.agent_id, action.after.capability),
                action.after.model_dump_json(),
            ),
        )
        action.status = "executed"
        self._save_action(db, action)
        self._audit(db, operator, target.agent_id, "action.executed", action_id)
        return ExecutionResult(action_id=action_id, outcome="succeeded", configuration=action.after)

    def audit(self, agent_id: str) -> list[AuditRecord]:
        self.registry.get(agent_id)
        with self._transaction(write=False) as db:
            records = [
                AuditRecord.model_validate_json(row[0])
                for row in db.execute("SELECT body FROM tower_audit ORDER BY id")
            ]
            return [record for record in records if record.agent_id == agent_id]
