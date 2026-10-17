"""Approved staging recovery through real HTTP routes and native Lens/Evals.

Run: uv run --with ../agenticlens --with ../agentic-evals python examples/incident_recovery.py
Pass --fail-verification to demonstrate escalation after remediation.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import agentic_evals as evals
import agenticlens as lens
from fastapi.testclient import TestClient

from agenticops_control_tower.api import ControlTowerAPI
from agenticops_control_tower.api.http import create_app
from agenticops_control_tower.config.models import Operator
from agenticops_control_tower.discovery import CapabilityDiscoveryService
from agenticops_control_tower.evidence import EvidenceStore
from agenticops_control_tower.incidents import IncidentService
from agenticops_control_tower.incidents.staging import StagingDependencyRuntime
from agenticops_control_tower.registry import AgentRegistry


def walkthrough(directory: Path, fail_verification: bool = False) -> dict:
    registry = AgentRegistry(str(directory / "tower.db"))
    store = EvidenceStore(registry, str(directory / "tower.db"))
    runtime = StagingDependencyRuntime(str(directory / "runtime.db"), "staging", "search")
    service = IncidentService(registry, store, str(directory / "tower.db"), {"staging": runtime})
    api = ControlTowerAPI(registry, CapabilityDiscoveryService(), evidence_store=store,
                          incident_service=service)
    client = TestClient(create_app(api, read_token="demo-reader", write_token="demo-writer",
                                  approval_token="demo-human"))
    writer = {"Authorization": "Bearer demo-writer"}
    human = {"Authorization": "Bearer demo-human"}

    def post(path, payload=None, headers=writer):
        response = client.post(path, json=payload or {}, headers=headers)
        response.raise_for_status()
        return response.json()

    post("/agents/register", dict(agent_id="staging", name="dependency fixture",
         environment="staging", runtime="sqlite-staging-fixture", framework="custom"))
    runtime.fail()

    def push_run(success):
        from agenticlens.models.trace import Span

        run = lens.Run(application_name="dependency fixture",
                       status="succeeded" if success else "failed", task_success=success,
                       error_type=None if success else "ConnectionError",
                       spans=[Span(name="search", span_type="tool_call", tool_name="search",
                                   status="succeeded" if success else "failed",
                                   error_type=None if success else "ConnectionError")])
        result = post("/evidence", dict(link=dict(agent_id="staging", source="agenticlens",
            source_version=lens.__version__, artifact_type="run", artifact_ref="run:" + run.run_id,
            run_id=run.run_id, observed_at=datetime.now(timezone.utc).isoformat()),
            artifact=run.model_dump(mode="json")))
        return run, result["record"]["record_id"]

    _, failed_id = push_run(False)
    incident = post("/incidents/detect", dict(agent_id="staging", evidence_id=failed_id))
    base = "/incidents/" + incident["incident_id"]
    post(base + "/investigate")
    preview = post(base + "/preview", dict(dependency="search"))
    digest = dict(preview_digest=preview["preview_digest"])
    post(base + "/approval", {**digest, "approved": True}, human)
    post(base + "/execute", digest)
    if fail_verification:
        runtime.fail()
    plan = service.get(incident["incident_id"], Operator(operator_id="demo", role="reader")).plan
    available = runtime.probe(plan)
    run, lens_id = push_run(available)
    from agentic_evals.models import EvaluationSample, EvalTrace, TestCase, TestSuite

    suite = TestSuite(name="dependency recovery", version="1", cases=[
        TestCase(id="dependency", name="Dependency responds", expected_output="ready")])
    report = evals.evaluate_suite(suite, [EvaluationSample(case_id="dependency",
        output="ready" if available else "unavailable", trace=EvalTrace(trace_id=run.trace_id))])
    gate = evals.evaluate_gate(report, evals.GateConfig())
    result = post("/evidence", dict(link=dict(agent_id="staging", source="agentic-evals",
        source_version=evals.__version__, artifact_type="evaluation_report",
        artifact_ref="eval:" + run.run_id, run_id=run.run_id,
        observed_at=datetime.now(timezone.utc).isoformat()), artifact=report.model_dump(mode="json"),
        gate=gate.model_dump(mode="json")))
    return post(base + "/verify", dict(lens_evidence_id=lens_id,
                                       evals_evidence_id=result["record"]["record_id"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-verification", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory() as directory:
        print(json.dumps(walkthrough(Path(directory), args.fail_verification), indent=2))
