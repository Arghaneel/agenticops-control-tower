"""Regenerate upstream contracts with agentic-evals==0.7.2 installed."""

import json
from pathlib import Path

from agentic_evals import __version__, gate_decision_schema, report_schema

assert __version__ == "0.7.2", "Use the pinned upstream contract producer"
ROOT = Path(__file__).resolve().parents[1]
for name, accessor in (
    ("evaluation-report", report_schema),
    ("gate-decision", gate_decision_schema),
):
    destination = ROOT / "src/agenticops_control_tower/schemas/evals" / f"{name}-1.0.schema.json"
    destination.write_text(
        json.dumps(accessor(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
