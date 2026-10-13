"""Shipped evidence examples stay valid against the current readers."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_python_push_example_runs(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(str(EXAMPLES / "push_ecosystem_evidence.py"), run_name="__main__")
    output = capsys.readouterr().out
    assert output.count(": available") == 4
    assert "agentic-chaos stale" in output
    assert "agenticlens fresh" in output


def test_manifest_pushes_over_http_cli(capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from agenticops_control_tower.api.http import create_app
    from agenticops_control_tower.cli.main import main

    client = TestClient(create_app())
    registration = json.loads((EXAMPLES / "sample_agent_registration.json").read_text())
    assert registration["agent_id"] == "payment-agent"
    assert client.post("/agents/register", json=registration).status_code == 201
    manifest = str(EXAMPLES / "evidence/manifest.json")
    assert main(["evidence", "ingest-manifest", manifest], client=client) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {**result, "submitted": 4, "created": 4, "unavailable": 0}
