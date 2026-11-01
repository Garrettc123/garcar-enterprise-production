"""Real PostgreSQL + pgvector integration tests.

These tests run only when MIGRATIONS_DATABASE_URL is configured. CI supplies an
isolated pgvector service; local unit-test runs safely skip this module.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from init_db import run_migrations
from src.governance.router import _canonical, configure_runtime_secrets, router

MIGRATION_URL = os.getenv("MIGRATIONS_DATABASE_URL")
pytestmark = pytest.mark.skipif(not MIGRATION_URL, reason="PostgreSQL integration database not configured")

AGENT_ID = "sales-agent"
AGENT_KEY = "a" * 40
OWNER_KEY = "b" * 40
EXECUTION_KEY = "c" * 40


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("ENVIRONMENT", "development")
    run_migrations()
    configure_runtime_secrets({
        "GARCAR_AGENT_API_KEYS": f"{AGENT_ID}:{AGENT_KEY}",
        "GARCAR_OWNER_API_KEY": OWNER_KEY,
        "GARCAR_EXECUTION_SIGNING_KEY": EXECUTION_KEY,
    })
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client
    configure_runtime_secrets({})


def test_postgres_governance_vector_memory_and_kill_switch(client):
    agent_headers = {"X-Agent-API-Key": AGENT_KEY}
    owner_headers = {"X-Owner-API-Key": OWNER_KEY}

    response = client.post("/v1/governance/kill-switch?enabled=false", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["kill_switch_active"] is False

    proposal_id = "ci-" + uuid.uuid4().hex
    proposal = {
        "proposal_id": proposal_id,
        "agent_id": AGENT_ID,
        "layer": "Revenue",
        "target_action": "integration_test_no_external_side_effect",
        "parameters": {"amount_cents": 100},
        "risk_score": 0.1,
        "requires_hitl": True,
    }
    response = client.post("/v1/governance/propose", json=proposal, headers=agent_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING_EVALUATION"

    response = client.post(
        "/v1/governance/evaluate",
        json={"proposal_id": proposal_id, "decision": "APPROVED", "note": "CI integration approval"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    authorization_token = response.json()["authorization_token"]

    receipt = {"success": True, "provider": "ci", "reference": proposal_id}
    signed = _canonical({"proposal_id": proposal_id, "executor_id": "ci-executor", "receipt": receipt})
    signature = hmac.new(EXECUTION_KEY.encode(), signed, hashlib.sha256).hexdigest()
    verification_payload = {
        "proposal_id": proposal_id,
        "authorization_token": authorization_token,
        "executor_id": "ci-executor",
        "receipt": receipt,
    }
    response = client.post(
        "/v1/governance/verify",
        json=verification_payload,
        headers={**agent_headers, "X-Execution-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["final_status"] == "EXECUTED_AND_VERIFIED"

    replay = client.post(
        "/v1/governance/verify",
        json=verification_payload,
        headers={**agent_headers, "X-Execution-Signature": signature},
    )
    assert replay.status_code == 409

    embedding = [1.0] + [0.0] * 1535
    stored = client.post(
        "/v1/memory/store",
        json={
            "namespace": AGENT_ID,
            "content": "Garcar pgvector integration test",
            "metadata": {"source": "ci"},
            "embedding": embedding,
        },
        headers=agent_headers,
    )
    assert stored.status_code == 201
    found = client.post(
        "/v1/memory/search",
        json={"namespace": AGENT_ID, "query_embedding": embedding, "match_threshold": 0.99, "limit": 3},
        headers=agent_headers,
    )
    assert found.status_code == 200
    assert any(item["content"] == "Garcar pgvector integration test" for item in found.json()["matches"])

    stopped = client.post("/v1/governance/kill-switch?enabled=true", headers=owner_headers)
    assert stopped.status_code == 200
    preflight = client.get("/v1/governance/execution-allowed", headers=agent_headers)
    assert preflight.status_code == 200
    assert preflight.json()["execution_allowed"] is False
