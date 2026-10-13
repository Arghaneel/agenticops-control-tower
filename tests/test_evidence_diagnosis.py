"""AgenticLens 0.7.0 diagnosis reports as native evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agenticops_control_tower.adapters import summarize_evidence
from agenticops_control_tower.adapters.evidence import artifact_type_for
from agenticops_control_tower.evidence.posture import native_tallies
from agenticops_control_tower.models.evidence import (
    EvidenceLink,
    EvidenceRecord,
    EvidenceSummary,
)

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "evidence" / "lens_diagnosis.json"


def _artifact() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return payload


def _link(**overrides: Any) -> EvidenceLink:
    values: dict[str, Any] = {
        "agent_id": "refund-agent",
        "source": "agenticlens",
        "source_version": "0.7.0",
        "artifact_type": "diagnosis_report",
        "artifact_ref": "diagnosis:incident-0042",
        "observed_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
        **overrides,
    }
    return EvidenceLink(**values)


def test_diagnosis_report_projects_attribution_without_evidence_payloads() -> None:
    result = summarize_evidence(_link(run_id="incident-0042"), _artifact())
    assert result.availability == "available"
    details = result.details
    assert details["attribution"]["faulty_step"] == "issue_refund"
    assert details["attribution"]["faulty_agent"] == "refunds"
    assert details["attribution"]["status"] == "attributed"
    assert details["summary"]["unrecovered"] == 3
    assert "diagnoses" not in details and "timeline" not in details


def test_diagnosis_report_rejects_mismatches() -> None:
    mismatch = summarize_evidence(_link(run_id="other"), _artifact())
    assert mismatch.availability == "unavailable" and mismatch.reason == "Run ID mismatch"
    wrong_source = summarize_evidence(
        _link(source="agentic-evals", artifact_type="diagnosis_report"), _artifact()
    )
    assert wrong_source.reason == "Source/type mismatch"
    broken = summarize_evidence(_link(), {**_artifact(), "attribution": {"status": "maybe"}})
    assert broken.availability == "unavailable"
    assert broken.reason is not None and "attribution.status" in broken.reason


def test_artifact_type_detection() -> None:
    assert artifact_type_for("agenticlens", _artifact()) == "diagnosis_report"
    assert artifact_type_for("agenticlens", {"run_id": "r"}) == "run"
    assert artifact_type_for("agentic-evals", _artifact()) == "evaluation_report"


def test_posture_counts_attribution_outcomes() -> None:
    summary = summarize_evidence(_link(), _artifact())
    record = EvidenceRecord(
        record_id="1",
        ingested_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
        ingested_by="test",
        summary=EvidenceSummary.model_validate(summary.model_dump()),
    )
    tallies = native_tallies("agenticlens", [record])
    assert tallies["status_counts"]["failed"] == 1
    assert tallies["attribution_counts"]["attributed"] == 1
    assert tallies["faulty_agents"] == ["refunds"]
