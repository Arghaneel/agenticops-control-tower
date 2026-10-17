"""Upstream schema parity and native-artifact validation regressions."""

import json
import subprocess
import sys
from copy import deepcopy
from importlib.resources import files

import pytest
from agentic_evals import (
    EvalTrace,
    EvaluationSample,
    GateConfig,
    evaluate_gate,
    evaluate_suite,
)
from agentic_evals import (
    TestCase as Case,
)
from agentic_evals import (
    TestSuite as Suite,
)

from agenticops_control_tower.adapters.evals_contract import validate_evals_artifact


@pytest.fixture
def report():
    suite = Suite(
        name="contract", version="1", cases=[Case(id="a", name="a", expected_output="ok")]
    )
    return evaluate_suite(
        suite, [EvaluationSample(case_id="a", output="wrong", trace=EvalTrace())]
    ).model_dump(mode="json")


@pytest.mark.parametrize("name", ["evaluation-report", "gate-decision"])
def test_packaged_schemas_are_exact_upstream_contracts(name):
    # An isolated interpreter avoids MCP's legacy sibling-venv import bootstrap.
    output = subprocess.check_output(
        [
            sys.executable,
            "-I",
            "-c",
            "import json; from agentic_evals import report_schema, gate_decision_schema; "
            "print(json.dumps({'evaluation-report': report_schema(), "
            "'gate-decision': gate_decision_schema()}))",
        ],
        text=True,
    )
    resource = files("agenticops_control_tower").joinpath("schemas").joinpath("evals")
    schema = json.loads(resource.joinpath(f"{name}-1.0.schema.json").read_text())
    assert schema == json.loads(output)[name]


@pytest.mark.parametrize("field", ["cases", "summary"])
def test_partial_reports_are_rejected(report, field):
    del report[field]
    with pytest.raises(ValueError, match="required"):
        validate_evals_artifact(report, "evaluation_report")


def test_nested_invalid_score_is_rejected_without_echoing_input(report):
    report["cases"][0]["scores"][0]["value"] = "SECRET_INVALID_VALUE"
    with pytest.raises(ValueError) as error:
        validate_evals_artifact(report, "evaluation_report")
    assert "/cases/0/scores/0/value" in str(error.value)
    assert "SECRET" not in str(error.value)


def test_unknown_fields_are_tolerated_without_mutation(report):
    report["future_field"] = {"$ref": "https://example.invalid/do-not-fetch"}
    report["summary"]["future_field"] = True
    report["cases"][0]["scores"][0]["future_field"] = True
    before = deepcopy(report)
    validate_evals_artifact(report, "evaluation_report")
    assert report == before


def test_unsupported_contract_and_artifact_types_are_rejected(report):
    report["schema_version"] = "2.0"
    with pytest.raises(ValueError, match="unsupported schema_version"):
        validate_evals_artifact(report, "evaluation_report")
    with pytest.raises(ValueError, match="Unsupported"):
        validate_evals_artifact({}, "unknown")


@pytest.mark.parametrize("gate", [{}, {"passed": "false", "reasons": [], "observed": {}}])
def test_invalid_gates_are_rejected(gate):
    with pytest.raises(ValueError, match="gate_decision"):
        validate_evals_artifact(gate, "gate_decision")


def test_a_structurally_valid_failed_gate_is_not_recomputed(report):
    from agentic_evals import EvaluationReport

    decision = evaluate_gate(EvaluationReport.model_validate(report), GateConfig())
    gate = decision.model_dump(mode="json")
    assert not gate["passed"]
    validate_evals_artifact(gate, "gate_decision")
    assert gate == decision.model_dump(mode="json")


@pytest.mark.parametrize("bad_gate", [False, True])
def test_tower_reader_marks_invalid_artifacts_unavailable(report, bad_gate):
    from agenticops_control_tower.adapters import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    link = EvidenceLink(
        agent_id="a",
        source="agentic-evals",
        source_version="0.7.2",
        artifact_type="evaluation_report",
        artifact_ref="eval:test",
        observed_at=report["created_at"],
    )
    gate = {"passed": False, "reasons": ["blocked"], "observed": {}}
    assert summarize_evidence(link, report, gate=gate).details["gate"]["passed"] is False
    if bad_gate:
        gate["passed"] = "false"
    else:
        report["cases"][0]["scores"][0]["value"] = 99
    result = summarize_evidence(link, report, gate=gate)
    assert result.availability == "unavailable"
    assert "native Evals" in result.reason


def test_tower_evidence_store_keeps_invalid_input_unavailable(report):
    from agenticops_control_tower.evidence import EvidenceStore
    from agenticops_control_tower.models import AgentRegistrationPayload, EvidenceIngestRequest
    from agenticops_control_tower.models.evidence import EvidenceLink
    from agenticops_control_tower.registry import AgentRegistry

    registry = AgentRegistry()
    registry.register(
        AgentRegistrationPayload(
            agent_id="a", name="a", environment="test", runtime="custom", framework="custom"
        )
    )
    report["cases"][0]["scores"][0]["value"] = 99
    request = EvidenceIngestRequest(
        link=EvidenceLink(
            agent_id="a",
            source="agentic-evals",
            source_version="0.7.2",
            artifact_type="evaluation_report",
            artifact_ref="eval:test",
            observed_at=report["created_at"],
        ),
        artifact=report,
    )
    record = EvidenceStore(registry).ingest(request).record
    assert record.summary.availability == "unavailable"
    assert record.summary.details == {}


@pytest.mark.parametrize("field", ["schema_version", "created_at"])
def test_tower_projection_accepts_defaulted_contract_fields(report, field):
    from agenticops_control_tower.adapters import summarize_evidence
    from agenticops_control_tower.models.evidence import EvidenceLink

    observed_at = report["created_at"]
    del report[field]
    link = EvidenceLink(
        agent_id="a",
        source="agentic-evals",
        source_version="0.7.2",
        artifact_type="evaluation_report",
        artifact_ref="eval:optional",
        observed_at=observed_at,
    )
    result = summarize_evidence(link, report)
    assert result.availability == "available"
    assert result.details["schema_version"] == "1.0"
    if field == "created_at":
        assert result.details["created_at"] is None


@pytest.mark.parametrize("nested", [False, True])
def test_missing_required_field_diagnostic_names_the_field(report, nested):
    if nested:
        del report["cases"][0]["scores"][0]["explanation"]
        expected = "/cases/0/scores/0/explanation"
    else:
        del report["cases"]
        expected = "/cases"
    with pytest.raises(ValueError, match=expected):
        validate_evals_artifact(report, "evaluation_report")
