"""CLI evidence pushes and posture reads against an in-process app."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agenticops_control_tower.api.http import create_app  # noqa: E402
from agenticops_control_tower.cli.main import main  # noqa: E402

OBSERVED = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()


@pytest.fixture
def api_client() -> TestClient:
    client = TestClient(create_app())
    client.post(
        "/agents/register",
        json={
            "agent_id": "payments",
            "name": "Payments",
            "environment": "staging",
            "runtime": "python",
            "framework": "custom",
        },
    )
    return client


def write(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return path


def run_cli(argv: list[str], client: TestClient, capsys: pytest.CaptureFixture[str]) -> object:
    assert main(argv, client=client) == 0
    return json.loads(capsys.readouterr().out)


REPORT = {
    "schema_version": "1.0",
    "suite_name": "suite",
    "suite_version": "1",
    "created_at": "2026-10-13T00:00:00Z",
    "summary": {
        "total_cases": 1,
        "passed_cases": 1,
        "failed_cases": 0,
        "pass_rate": 1,
        "average_score": 1,
    },
}


def test_ingest_one_artifact_with_gate_then_read(
    tmp_path: Path, api_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    report = write(tmp_path, "report.json", REPORT)
    gate = write(tmp_path, "gate.json", {"passed": True, "reasons": [], "observed": {}})
    result = run_cli(
        [
            "evidence",
            "ingest",
            "payments",
            "agentic-evals",
            str(report),
            "--source-version",
            "0.7.1",
            "--artifact-ref",
            "eval:suite:1",
            "--observed-at",
            OBSERVED,
            "--gate",
            str(gate),
            "--run-id",
            "run-1",
        ],
        api_client,
        capsys,
    )
    assert result["created"] is True
    link = result["record"]["summary"]["link"]
    assert link["artifact_type"] == "evaluation_report"
    assert link["run_id"] == "run-1"
    assert result["record"]["summary"]["details"]["gate"]["passed"] is True
    history = run_cli(["evidence", "history", "payments", "--limit", "1"], api_client, capsys)
    assert len(history) == 1
    posture = run_cli(["evidence", "posture", "payments"], api_client, capsys)
    evals = next(s for s in posture["sources"] if s["source"] == "agentic-evals")
    assert evals["summary"]["gate_counts"]["passed"] == 1
    fleet = run_cli(["posture", "--environment", "staging"], api_client, capsys)
    assert fleet["total_agents"] == 1


def test_manifest_reads_relative_files_client_side(
    tmp_path: Path, api_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "artifacts").mkdir()
    write(
        tmp_path / "artifacts",
        "run.json",
        {"schema_version": "1.0", "run_id": "r1", "application_name": "a", "status": "failed"},
    )
    link = {
        "agent_id": "payments",
        "source": "agenticlens",
        "source_version": "0.6.1",
        "artifact_type": "run",
        "artifact_ref": "run:r1",
        "observed_at": OBSERVED,
    }
    manifest = write(
        tmp_path,
        "manifest.json",
        {
            "entries": [
                {"link": link, "artifact_path": "artifacts/run.json"},
                {"link": {**link, "artifact_ref": "run:missing"}},
            ]
        },
    )
    result = run_cli(["evidence", "ingest-manifest", str(manifest)], api_client, capsys)
    assert result["submitted"] == 2
    assert result["created"] == 2
    assert result["unavailable"] == 1
    again = run_cli(["evidence", "ingest-manifest", str(manifest)], api_client, capsys)
    assert again["created"] == 0


def test_sidecar_journal_is_pushed_decision_by_decision(
    tmp_path: Path, api_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    events = [
        {"kind": "proposed", "timestamp": OBSERVED},
        {
            "kind": "decision",
            "sequence": 2,
            "task_id": "t",
            "timestamp": OBSERVED,
            "payload": {"decision": {"decision_id": "d1", "status": "PAUSE", "risk": None}},
        },
        {
            "kind": "decision",
            "sequence": 3,
            "task_id": "t",
            "timestamp": OBSERVED,
            "payload": {"decision": {"status": "ALLOW", "risk": "LOW", "reason": "ok"}},
        },
    ]
    journal = write(tmp_path, "journal.json", {"events": events})
    result = run_cli(
        [
            "evidence",
            "ingest-sidecar-journal",
            "payments",
            str(journal),
            "--source-version",
            "0.7.0",
        ],
        api_client,
        capsys,
    )
    refs = [r["summary"]["link"]["artifact_ref"] for r in result["records"]]
    assert refs == ["decision:d1", "decision:t:3"]
    # The first decision lacks the native `reason` field and is recorded as unavailable.
    assert result["unavailable"] == 1


def test_errors_and_snapshot_rejection(
    tmp_path: Path, api_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = write(tmp_path, "a.json", {})
    with pytest.raises(SystemExit, match="404"):
        main(
            [
                "evidence",
                "ingest",
                "absent",
                "agentic-chaos",
                str(artifact),
                "--source-version",
                "0.5.1",
                "--artifact-ref",
                "c",
            ],
            client=api_client,
        )
    with pytest.raises(SystemExit):
        main(
            [
                "--snapshot",
                "examples/sample_fleet_snapshot.json",
                "evidence",
                "ingest-manifest",
                "m",
            ]
        )


def test_ingest_detects_lens_diagnosis_reports(
    api_client: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = Path(__file__).resolve().parents[1] / "examples" / "evidence" / "lens_diagnosis.json"
    artifact = json.loads(sample.read_text(encoding="utf-8"))
    result = run_cli(
        [
            "evidence",
            "ingest",
            "payments",
            "agenticlens",
            str(sample),
            "--source-version",
            "0.7.0",
            "--artifact-ref",
            "lens:diagnosis:1",
            "--run-id",
            artifact["run_id"],
            "--observed-at",
            OBSERVED,
        ],
        api_client,
        capsys,
    )
    summary = result["record"]["summary"]  # type: ignore[index]
    assert summary["link"]["artifact_type"] == "diagnosis_report"
    assert summary["availability"] == "available"
    assert summary["details"]["attribution"]["faulty_step"] == "issue_refund"
