"""Supported deterministic staging runtime: a durable local dependency fixture.

This is deliberately not a production process manager. Its SQLite transaction
restores one fixture dependency, with a bounded database lock wait and a durable
idempotency receipt in the same commit. No shell or network dispatch is involved.
"""

import sqlite3
from typing import Literal

from agenticops_control_tower.incidents.models import RecoveryPlan


class StagingDependencyRuntime:
    def __init__(self, database_path: str, agent_id: str, dependency: str) -> None:
        self.database_path = database_path
        self.agent_id = agent_id
        self.dependency = dependency
        with sqlite3.connect(database_path, timeout=1) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS staging_dependencies "
                "(agent TEXT, dependency TEXT, available INTEGER, "
                "PRIMARY KEY(agent, dependency))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS staging_receipts "
                "(id TEXT PRIMARY KEY, agent TEXT, dependency TEXT)"
            )
            db.execute(
                "INSERT OR IGNORE INTO staging_dependencies VALUES (?, ?, 1)",
                (agent_id, dependency),
            )

    def supports(self, agent_id: str, dependency: str) -> bool:
        return agent_id == self.agent_id and dependency == self.dependency

    def fail(self) -> None:
        """Deterministic fault injection for the operator walkthrough."""
        with sqlite3.connect(self.database_path, timeout=1) as db:
            db.execute(
                "UPDATE staging_dependencies SET available=0 WHERE agent=? AND dependency=?",
                (self.agent_id, self.dependency),
            )

    def execute(self, incident_id: str, plan: RecoveryPlan) -> Literal["succeeded"]:
        if not self.supports(plan.agent_id, plan.dependency):
            raise ValueError("Unsupported staging target")
        with sqlite3.connect(self.database_path, timeout=plan.timeout_seconds) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT agent, dependency FROM staging_receipts WHERE id=?", (incident_id,)
            ).fetchone()
            if previous is not None and previous != (self.agent_id, self.dependency):
                raise ValueError("Idempotency key belongs to a different target")
            if previous is None:
                db.execute(
                    "UPDATE staging_dependencies SET available=1 WHERE agent=? AND dependency=?",
                    (self.agent_id, self.dependency),
                )
                db.execute(
                    "INSERT INTO staging_receipts VALUES (?, ?, ?)",
                    (incident_id, self.agent_id, self.dependency),
                )
        return "succeeded"

    def probe(self, plan: RecoveryPlan) -> bool:
        if not self.supports(plan.agent_id, plan.dependency):
            return False
        with sqlite3.connect(self.database_path, timeout=plan.timeout_seconds) as db:
            row = db.execute(
                "SELECT available FROM staging_dependencies WHERE agent=? AND dependency=?",
                (self.agent_id, self.dependency),
            ).fetchone()
            return row == (1,)
