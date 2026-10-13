"""Authenticated evidence ingestion, history and posture over HTTP."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from agenticops_control_tower.api.http import MAX_EVIDENCE_BYTES, create_app  # noqa: E402

READER = {"Authorization": "Bearer reader"}
WRITER = {"Authorization": "Bearer writer"}
OBSERVED = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()


def payload(agent_id: str = "payments", **link: object) -> dict:
    body = {
        "link": {
            "agent_id": agent_id,
            "source": "agenticlens",
            "source_version": "0.6.1",
            "artifact_type": "run",
            "artifact_ref": "run:r1",
            "run_id": "r1",
            "observed_at": OBSERVED,
            **link,
        },
        "artifact": {
            "schema_version": "1.0",
            "run_id": "r1",
            "application_name": "payments",
            "status": "failed",
        },
    }
    return body


def client(database: str | None = None) -> TestClient:
    result = TestClient(
        create_app(database_path=database, read_token="reader", write_token="writer")
    )
    response = result.post(
        "/agents/register",
        json={
            "agent_id": "payments",
            "name": "Payments",
            "environment": "staging",
            "runtime": "python",
            "framework": "custom",
            "status": "healthy",
        },
        headers=WRITER,
    )
    assert response.status_code == 201
    return result


def test_writer_ingests_and_retries_are_idempotent() -> None:
    http = client()
    first = http.post("/evidence", json=payload(), headers=WRITER)
    assert first.status_code == 201
    assert first.json()["created"] is True
    assert first.json()["record"]["ingested_by"] == "http-writer"
    retry = http.post("/evidence", json=payload(), headers=WRITER)
    assert retry.status_code == 200
    assert retry.json()["created"] is False
    assert retry.json()["record"]["record_id"] == first.json()["record"]["record_id"]


def test_reader_cannot_ingest_and_anonymous_is_rejected() -> None:
    http = client()
    assert http.post("/evidence", json=payload(), headers=READER).status_code == 403
    assert http.post("/evidence", json=payload()).status_code == 401
    assert http.get("/agents/payments/evidence/history", headers=READER).json() == []


def test_history_and_posture_reads() -> None:
    http = client()
    http.post("/evidence", json=payload(), headers=WRITER)
    history = http.get(
        "/agents/payments/evidence/history?source=agenticlens&limit=5", headers=READER
    ).json()
    assert [r["summary"]["details"]["status"] for r in history] == ["failed"]
    assert (
        http.get("/agents/payments/evidence/history?source=agentic-chaos", headers=READER).json()
        == []
    )
    posture = http.get("/agents/payments/evidence", headers=READER).json()
    sources = {s["source"]: s for s in posture["sources"]}
    assert posture["reported_health"] == "healthy"
    assert sources["agenticlens"]["freshness"] == "fresh"
    assert sources["agenticlens"]["summary"]["status_counts"]["failed"] == 1
    assert sources["agentic-evals"]["freshness"] == "missing"
    stale = http.get("/agents/payments/evidence?stale_after_seconds=1", headers=READER).json()
    assert {s["source"]: s["freshness"] for s in stale["sources"]}["agenticlens"] == "stale"
    fleet = http.get("/posture?environment=staging", headers=READER).json()
    assert fleet["total_agents"] == 1
    lens = next(s for s in fleet["sources"] if s["source"] == "agenticlens")
    assert lens["fresh_agents"] == ["payments"]
    assert http.get("/status", headers=READER).json()["healthy_agents"] == 1


def test_validation_errors_and_unknown_deployments() -> None:
    http = client()
    assert http.post("/evidence", json=payload("absent"), headers=WRITER).status_code == 404
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    response = http.post("/evidence", json=payload(observed_at=future), headers=WRITER)
    assert response.status_code == 422
    assert "future" in response.json()["detail"]
    assert http.post("/evidence", json={"link": {}}, headers=WRITER).status_code == 422
    for query in ["limit=0", "limit=501", "source=unknown"]:
        assert (
            http.get(f"/agents/payments/evidence/history?{query}", headers=READER).status_code
            == 422
        )
    for path in ["/agents/payments/evidence", "/posture"]:
        assert http.get(f"{path}?stale_after_seconds=0", headers=READER).status_code == 422
    assert http.get("/agents/absent/evidence/history", headers=READER).status_code == 404


def test_oversized_and_unsized_bodies_are_rejected() -> None:
    http = client()
    body = payload()
    body["artifact"]["padding"] = "x" * MAX_EVIDENCE_BYTES
    assert http.post("/evidence", json=body, headers=WRITER).status_code == 413

    def chunks():
        yield json.dumps(payload()).encode()

    response = http.post(
        "/evidence",
        content=chunks(),
        headers={**WRITER, "Content-Type": "application/json"},
    )
    assert response.status_code == 411


def test_unavailable_artifacts_are_recorded_honestly() -> None:
    http = client()
    body = payload()
    body["artifact"] = None
    record = http.post("/evidence", json=body, headers=WRITER).json()["record"]
    assert record["summary"]["availability"] == "unavailable"
    assert record["summary"]["reason"] == "No artifact supplied"


def test_sqlite_evidence_survives_app_restart(tmp_path: Path) -> None:
    database = str(tmp_path / "tower.sqlite")
    client(database).post("/evidence", json=payload(), headers=WRITER)
    restarted = TestClient(
        create_app(database_path=database, read_token="reader", write_token="writer")
    )
    history = restarted.get("/agents/payments/evidence/history", headers=READER).json()
    assert len(history) == 1


def test_body_limit_runs_before_parsing_and_authorization() -> None:
    import asyncio

    from agenticops_control_tower.api.limits import BodySizeLimit

    parsed: list[bytes] = []

    async def downstream(scope, receive, send) -> None:
        while True:
            message = await receive()
            parsed.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def call(headers: list[tuple[bytes, bytes]], chunks: list[bytes]) -> int:
        limit = BodySizeLimit(downstream, paths=frozenset({"/evidence"}), max_bytes=10)
        messages = [
            {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
            for i, chunk in enumerate(chunks)
        ]
        sent: list[dict] = []

        async def receive() -> dict:
            return messages.pop(0)

        async def send(message: dict) -> None:
            sent.append(message)

        scope = {"type": "http", "method": "POST", "path": "/evidence", "headers": headers}
        await limit(scope, receive, send)
        return sent[0]["status"]

    # A body exceeding its declared length is cut off once the limit is crossed.
    assert asyncio.run(call([(b"content-length", b"5")], [b"123456", b"78901"])) == 413
    assert asyncio.run(call([(b"content-length", b"5")], [b"12345"])) == 200
    assert asyncio.run(call([], [b"1"])) == 411
    assert asyncio.run(call([(b"content-length", b"x")], [b"1"])) == 413
    # Without credentials, oversized bodies are still rejected before authorization.
    http = client()
    assert http.post("/evidence", content=b"x" * (MAX_EVIDENCE_BYTES + 1)).status_code == 413
