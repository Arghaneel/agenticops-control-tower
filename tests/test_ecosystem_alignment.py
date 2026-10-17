"""Contract safety independent of optional sibling installations."""

from datetime import datetime, timezone

import pytest

from agenticops_control_tower.adapters import ADAPTER_NAMES, summarize_evidence
from agenticops_control_tower.errors import AgentNotFoundError
from agenticops_control_tower.models import AgentRegistrationPayload
from agenticops_control_tower.models.evidence import EvidenceLink
from agenticops_control_tower.snapshot import create_api


def link(**changes: object) -> EvidenceLink:
    data = dict(
        agent_id="deployment-a",
        source="agentic-sidecar",
        source_version="0.6.0",
        artifact_type="decision",
        artifact_ref="decision:1",
        observed_at=datetime.now(timezone.utc),
    )
    data.update(changes)
    return EvidenceLink.model_validate(data)


def test_evals_is_explicitly_catalogued() -> None:
    assert "agentic-evals" in ADAPTER_NAMES


@pytest.mark.parametrize(
    "status", ["ALLOW", "WARN", "BLOCK", "CHALLENGE", "REPLAN", "PAUSE", "ESCALATE"]
)
def test_supervision_outcomes_never_change_health(status: str) -> None:
    api = create_api()
    api.register_agent(
        AgentRegistrationPayload(
            agent_id="deployment-a",
            name="A",
            environment="test",
            runtime="custom",
            framework="custom",
            status="healthy",
        )
    )
    summary = api.summarize_evidence(
        link(), {"status": status, "risk": None, "reason": "producer decision"}
    )
    assert summary.availability == "available"
    assert summary.details["status"] == status
    assert summary.details["risk"] is None
    assert api.get_status().healthy_agents == 1
    assert api.get_agent("deployment-a").heartbeat_count == 0


def test_attribution_requires_registered_deployment() -> None:
    with pytest.raises(AgentNotFoundError):
        create_api().summarize_evidence(link(), {})


@pytest.mark.parametrize(
    "artifact", [None, {}, {"status": "healthy", "risk": "HIGH", "reason": "invalid decision"}]
)
def test_bad_or_missing_artifacts_are_unavailable(artifact: dict | None) -> None:
    result = summarize_evidence(link(), artifact)
    assert result.availability == "unavailable"
    assert result.details == {}
    assert result.reason


def test_unsupported_types_schema_and_identity() -> None:
    assert summarize_evidence(link(artifact_type="run"), {}).availability == "unavailable"
    native_run = dict(schema_version="1.0", run_id="run-a", application_name="app", status="failed")
    run_link = link(
        source="agenticlens", source_version="0.5.0", artifact_type="run", run_id="run-b"
    )
    assert summarize_evidence(run_link, native_run).availability == "unavailable"
    assert (
        summarize_evidence(run_link.model_copy(update={"run_id": "run-a"}), native_run).availability
        == "available"
    )
    assert (
        summarize_evidence(run_link, dict(native_run, schema_version="2.0")).availability
        == "unavailable"
    )
    assert summarize_evidence(link(spec_version="0.4-draft"), {}).availability == "unavailable"


def test_evaluation_gate_is_preserved_without_recomputation() -> None:
    report = dict(
        schema_version="1.0",
        suite_name="suite",
        suite_version="1",
        cases=[],
        created_at="2026-10-10T12:00:00Z",
        summary=dict(
            total_cases=1,
            passed_cases=0,
            failed_cases=1,
            pass_rate=0,
            average_score=0,
            average_latency_ms=0,
        ),
    )
    eval_link = link(
        source="agentic-evals", source_version="0.7.0", artifact_type="evaluation_report"
    )
    assert summarize_evidence(eval_link, report).details["gate"] is None
    gate = dict(passed=False, reasons=["source policy failed"], observed={"pass_rate": 0})
    assert summarize_evidence(eval_link, report, gate=gate).details["gate"] == gate
    assert summarize_evidence(eval_link, report, gate={}).availability == "unavailable"


def test_sidecar_decision_identity_and_trigger_survive_readback():
    artifact = {
        "decision_id": "decision-1",
        "status": "ALLOW",
        "risk": "LOW",
        "reason": "Approved once",
        "causal_link": "paused-decision",
        "trigger_details": {"tool_name": "refund", "arguments": {"amount": 120}},
    }
    result = summarize_evidence(link(source_version="0.7.0"), artifact)
    assert result.availability == "available"
    assert result.details["decision_id"] == "decision-1"
    assert result.details["causal_link"] == "paused-decision"
    assert result.details["trigger_details"] == artifact["trigger_details"]


def test_invalid_sidecar_decision_identity_is_unavailable():
    result = summarize_evidence(
        link(), {"decision_id": "", "status": "BLOCK", "risk": None, "reason": "Denied"}
    )
    assert result.availability == "unavailable"


def test_unavailable_reason_names_the_failing_native_field_without_values() -> None:
    result = summarize_evidence(
        link(), {"status": "MAYBE", "risk": "secret-value", "reason": "Denied"}
    )
    assert result.availability == "unavailable"
    assert result.reason is not None
    assert result.reason.startswith("Invalid or unsupported producer artifact: ")
    assert "status" in result.reason
    assert "(+1 more)" in result.reason
    assert "secret-value" not in result.reason


def test_lens_run_projects_correlation_fields_without_span_payloads() -> None:
    run = {
        "schema_version": "1.0",
        "run_id": "run-a",
        "trace_id": "trace-a",
        "application_name": "payments",
        "status": "failed",
        "started_at": "2026-10-13T10:00:00Z",
        "completed_at": "2026-10-13T10:00:02Z",
        "error_type": "DependencyUnavailable",
        "spans": [
            {"span_id": "s1", "name": "plan", "span_type": "planning", "status": "succeeded"},
            {
                "span_id": "s2",
                "name": "charge",
                "span_type": "tool_call",
                "tool_name": "payments_api",
                "status": "failed",
                "error_type": "ConnectionError",
                "error_message": "token=secret",
                "input_data": {"card": "secret"},
            },
        ],
    }
    run_link = link(source="agenticlens", source_version="0.6.1", artifact_type="run")
    details = summarize_evidence(run_link, run).details
    assert details["trace_id"] == "trace-a"
    assert details["error_type"] == "DependencyUnavailable"
    assert details["span_count"] == 2
    assert details["tool_names"] == ["payments_api"]
    assert details["failed_spans"] == [
        {
            "span_id": "s2",
            "name": "charge",
            "span_type": "tool_call",
            "tool_name": "payments_api",
            "error_type": "ConnectionError",
        }
    ]
    assert "secret" not in str(details)
    assert "spans" not in details


def test_legacy_lens_run_without_optional_fields_remains_available() -> None:
    run_link = link(source="agenticlens", source_version="0.5.0", artifact_type="run")
    native = dict(schema_version="1.0", run_id="run-a", application_name="app", status="running")
    details = summarize_evidence(run_link, native).details
    assert details["span_count"] == 0
    assert details["failed_spans"] == []
    assert details["trace_id"] is None
