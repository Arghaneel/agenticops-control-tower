"""Lens 1.1 diagnosis projection stays compatible without a Lens dependency."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agenticops_control_tower.adapters import summarize_evidence
from agenticops_control_tower.models.evidence import EvidenceLink


@pytest.mark.parametrize("version,available", [("1.0", True), ("1.1", True), ("2.0", False)])
def test_lens_diagnosis_versions(version: str, available: bool) -> None:
    artifact = json.loads(
        (Path(__file__).resolve().parents[1] / "examples/evidence/lens_diagnosis.json").read_text()
    )
    artifact["schema_version"] = version
    link = EvidenceLink(
        agent_id="agent",
        source="agenticlens",
        source_version="0.7.1",
        artifact_type="diagnosis_report",
        artifact_ref="diagnosis:test",
        run_id=artifact["run_id"],
        observed_at=datetime.now(timezone.utc),
    )
    result = summarize_evidence(link, artifact)
    assert (result.availability == "available") == available
