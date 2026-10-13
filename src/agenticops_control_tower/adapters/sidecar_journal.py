"""Extract native decision snapshots from Sidecar runtime journal exports.

This parses JSON objects, JSON export arrays and JSONL. It does not verify the
journal hash chain, infer tool completion or map task IDs to deployments.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JournalDecision(BaseModel):
    """One producer decision and the journal timestamp it was recorded at."""

    task_id: str | None
    sequence: int | None
    recorded_at: datetime
    decision: dict[str, Any]


def _events(content: str) -> list[Any]:
    try:
        recording = json.loads(content)
    except json.JSONDecodeError:
        return [json.loads(line) for line in content.splitlines() if line.strip()]
    if isinstance(recording, list):
        return recording
    if isinstance(recording, dict):
        events = recording.get("events", [recording])
        return events if isinstance(events, list) else []
    return []


def sidecar_journal_decisions(content: str) -> list[JournalDecision]:
    """Return decision payloads in journal order; non-decision events are skipped."""
    decisions: list[JournalDecision] = []
    for event in _events(content):
        if not isinstance(event, dict) or event.get("kind") != "decision":
            continue
        payload = event.get("payload")
        decision = payload.get("decision") if isinstance(payload, dict) else None
        if not isinstance(decision, dict) or "timestamp" not in event:
            continue
        decisions.append(
            JournalDecision(
                task_id=event.get("task_id"),
                sequence=event.get("sequence"),
                recorded_at=event["timestamp"],
                decision=decision,
            )
        )
    return decisions
