"""Evidence posture models keep producer sources explicit."""

from agenticops_control_tower.models import EVIDENCE_SOURCES, EvidenceIngestRequest


def test_evidence_sources_cover_the_four_native_readers() -> None:
    assert EVIDENCE_SOURCES == ("agenticlens", "agentic-evals", "agentic-sidecar", "agentic-chaos")


def test_ingest_request_allows_absent_artifact_for_honest_unavailable_records() -> None:
    request = EvidenceIngestRequest.model_validate(
        {
            "link": {
                "agent_id": "a",
                "source": "agentic-chaos",
                "source_version": "0.5.1",
                "artifact_type": "chaos_report",
                "artifact_ref": "chaos:1",
                "observed_at": "2026-10-13T00:00:00Z",
            }
        }
    )
    assert request.artifact is None
    assert request.gate is None
