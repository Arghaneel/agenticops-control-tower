"""Offline snapshots carry evidence evaluated as of capture time."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agenticops_control_tower.cli.main import main
from agenticops_control_tower.errors import SnapshotLoadError
from agenticops_control_tower.snapshot import load_snapshot, read_snapshot

SAMPLE = Path(__file__).resolve().parents[1] / "examples/sample_fleet_snapshot.json"


def test_sample_snapshot_evidence_posture_is_relative_to_capture() -> None:
    snapshot = read_snapshot(SAMPLE)
    api = load_snapshot(SAMPLE)
    posture = api.agent_posture("payment-agent", now=snapshot.captured_at)
    sources = {s.source: s for s in posture.sources}
    assert sources["agenticlens"].freshness == "fresh"
    assert sources["agenticlens"].summary["failed_tool_names"] == ["payments_api"]
    assert sources["agentic-chaos"].freshness == "stale"
    assert sources["agentic-evals"].summary["gate_counts"]["failed"] == 1
    assert all(r.ingested_by == "snapshot" for r in api.evidence_history("payment-agent"))
    assert api.get_status().total_agents == 2


def test_snapshot_cli_reads_posture_and_history(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--snapshot", str(SAMPLE), "posture"]) == 0
    fleet = json.loads(capsys.readouterr().out)
    lens = next(s for s in fleet["sources"] if s["source"] == "agenticlens")
    assert lens["fresh_agents"] == ["payment-agent"]
    assert lens["missing_agents"] == ["support-agent"]
    assert main(["--snapshot", str(SAMPLE), "evidence", "posture", "payment-agent"]) == 0
    assert json.loads(capsys.readouterr().out)["agent_id"] == "payment-agent"
    argv = ["--snapshot", str(SAMPLE), "evidence", "history", "payment-agent"]
    assert main([*argv, "--source", "agentic-sidecar"]) == 0
    history = json.loads(capsys.readouterr().out)
    assert [r["summary"]["details"]["status"] for r in history] == ["ESCALATE"]


def test_snapshot_evidence_for_unknown_deployment_fails_to_load(tmp_path: Path) -> None:
    data = json.loads(SAMPLE.read_text())
    data["evidence"][0]["link"]["agent_id"] = "absent"
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data))
    with pytest.raises(SnapshotLoadError, match="absent"):
        load_snapshot(path)
