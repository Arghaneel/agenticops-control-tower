"""Validate installed-wheel resources without runtime producer dependencies."""

import sys
from pathlib import Path

import agenticops_control_tower
from agenticops_control_tower.adapters.evals_contract import validate_evals_artifact

assert (
    Path(agenticops_control_tower.__file__).parent
    != Path(__file__).resolve().parents[1] / "src/agenticops_control_tower"
)
report = {
    "suite_name": "wheel-smoke",
    "suite_version": "1",
    "cases": [],
    "summary": {
        "total_cases": 0,
        "passed_cases": 0,
        "failed_cases": 0,
        "pass_rate": 0,
        "average_score": 0,
        "average_latency_ms": 0,
    },
}
validate_evals_artifact(report, "evaluation_report")
validate_evals_artifact({"passed": False, "reasons": ["blocked"], "observed": {}}, "gate_decision")
assert "agentic_evals" not in sys.modules
assert "agenticlens" not in sys.modules
print("Installed native Evals contract resources validated without siblings")
