"""Sidecar journal extraction stays a parser, not a journal verifier."""

import json

from agenticops_control_tower.adapters import sidecar_journal_decisions


def decision_event(sequence: int, status: str = "ALLOW") -> dict:
    return {
        "sequence": sequence,
        "kind": "decision",
        "task_id": "refund-demo",
        "timestamp": f"2026-10-12T04:41:1{sequence}+00:00",
        "payload": {"decision": {"decision_id": f"d{sequence}", "status": status}},
    }


def test_extracts_decisions_in_order_and_skips_other_events() -> None:
    content = json.dumps(
        {"events": [{"kind": "proposed"}, decision_event(2, "PAUSE"), decision_event(3)]}
    )
    decisions = sidecar_journal_decisions(content)
    assert [entry.decision["decision_id"] for entry in decisions] == ["d2", "d3"]
    assert decisions[0].task_id == "refund-demo"
    assert decisions[0].sequence == 2
    assert decisions[0].recorded_at.isoformat() == "2026-10-12T04:41:12+00:00"


def test_jsonl_and_export_arrays_are_supported() -> None:
    jsonl = "\n".join(json.dumps(decision_event(n)) for n in (1, 2)) + "\n"
    assert len(sidecar_journal_decisions(jsonl)) == 2
    assert len(sidecar_journal_decisions(json.dumps([decision_event(1)]))) == 1


def test_malformed_decision_events_are_skipped() -> None:
    events = [
        {"kind": "decision", "timestamp": "2026-10-12T00:00:00Z", "payload": {}},
        {"kind": "decision", "payload": {"decision": {"status": "ALLOW"}}},
        {"kind": "decision", "timestamp": "2026-10-12T00:00:00Z", "payload": "x"},
        "not-an-event",
    ]
    assert sidecar_journal_decisions(json.dumps(events)) == []
    invalid_types = [
        {**decision_event(1), "timestamp": "not-a-time"},
        {**decision_event(2), "sequence": "two"},
        {**decision_event(3), "task_id": 3},
        decision_event(4),
    ]
    decisions = sidecar_journal_decisions(json.dumps(invalid_types))
    assert [entry.decision["decision_id"] for entry in decisions] == ["d4"]
    assert sidecar_journal_decisions(json.dumps({"events": "bad"})) == []
    assert sidecar_journal_decisions("42") == []


def test_v09_authority_journal_is_compatible_and_redacted_summaries_are_not_native():
    from pathlib import Path

    native = json.loads((Path(__file__).parent / "fixtures/sidecar-v09-authority.json").read_text())
    decisions = sidecar_journal_decisions(json.dumps(native["events"]))
    assert len(decisions) == 1
    assert decisions[0].decision == native["correlated"][0]["decision"]
    assert decisions[0].decision["status"] == "BLOCK"
    assert "revoked" in decisions[0].decision["reason"]
    event = next(e for e in native["events"] if e["kind"] == "decision")
    authority = event["payload"]["context"]["metadata"]["sidecar.authority"]
    assert authority["agent_id"] == "refund-agent"
    assert authority["grant_id"] and authority["parent_intent_id"]
    assert sidecar_journal_decisions(json.dumps(native["redacted"])) == []
