"""Example readback supports demo JSON, native export arrays and single/multiple-event JSONL."""

import json
import runpy
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("format", ["recording", "export-array", "single-jsonl", "multiple-jsonl"])
def test_journal_example_reads_decisions_without_changing_health(
    tmp_path, monkeypatch, capsys, format
):
    event = {
        "kind": "decision",
        "timestamp": "2026-10-11T12:00:00+00:00",
        "task_id": "task",
        "payload": {
            "decision": {
                "decision_id": "decision-1",
                "status": "BLOCK",
                "risk": "HIGH",
                "reason": "Denied",
            }
        },
    }
    if format == "recording":
        content = json.dumps({"events": [event]})
    elif format == "export-array":
        content = json.dumps([{"kind": "completed"}, event])
    elif format == "single-jsonl":
        content = json.dumps(event) + "\n"
    else:
        content = json.dumps({"kind": "completed"}) + "\n" + json.dumps(event) + "\n"
    path = tmp_path / "journal"
    path.write_text(content)
    script = Path(__file__).resolve().parents[1] / "examples/inspect_sidecar_journal.py"
    monkeypatch.setattr(sys, "argv", [str(script), str(path), "--source-version", "0.7.0"])
    runpy.run_path(str(script), run_name="__main__")
    output = capsys.readouterr().out
    assert '"decision_id": "decision-1"' in output
    assert '"status": "BLOCK"' in output
    assert "Healthy deployments: 1" in output
