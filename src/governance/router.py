from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator
import math

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pgvector.psycopg import register_vector
from pgvector import Vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .policy import evaluate_policy

router = APIRouter(prefix="/v1", tags=["governance"])
TOKEN_TTL_SECONDS = int(os.getenv("GARCAR_AUTHORIZATION_TTL_SECONDS", "300"))
_runtime_secrets: dict[str, str] = {}


def configure_runtime_secrets(values: dict[str, Any]) -> None:
    """Receive secrets loaded by the application lifespan from Vault."""
    global _runtime_secrets
    _runtime_secrets = {key: str(value) for key, value in values.items() if value is not None}


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise HTTPException(status_code=503, detail="Governance database is not configured")
    return value


@contextmanager
def db_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(_database_url(), row_factory=dict_row)
    register_vector(conn)
    try:
        yield conn
    finally:
        conn.close()


def _secret(name: str) -> str:
    # Production secrets must come from the Vault-loaded lifespan context.
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        return _runtime_secrets.get(name, "")
    return _runtime_secrets.get(name) or os.getenv(name, "")


def _constant_time_key_match(candidate: str, configured: list[str]) -> bool:
    candidate_digest = hashlib.sha256(candidate.encode()).digest()
    return any(hmac.compare_digest(candidate_digest, hashlib.sha256(key.encode()).digest()) for key in configured if key)


def _configured_agent_keys() -> list[tuple[str, str]]:
    """Return (agent_id, key) pairs; legacy bare keys get a stable non-secret identity."""
    pairs: list[tuple[str, str]] = []
    for item in _secret("GARCAR_AGENT_API_KEYS").split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            agent_id, key = item.split(":", 1)
            agent_id = agent_id.strip()
            key = key.strip()
        else:
            key = item
            agent_id = "agent_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        if agent_id and len(key) >= 32:
            pairs.append((agent_id, key))
    return pairs


def require_agent(x_agent_api_key: str = Header(default="", alias="X-Agent-API-Key")) -> str:
    if len(x_agent_api_key) < 32:
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
    candidate_digest = hashlib.sha256(x_agent_api_key.encode()).digest()
    for agent_id, key in _configured_agent_keys():
        if hmac.compare_digest(candidate_digest, hashlib.sha256(key.encode()).digest()):
            return agent_id
    raise HTTPException(status_code=401, detail="Invalid agent credentials")


def _require_owned_namespace(namespace: str, agent_id: str) -> None:
    if not hmac.compare_digest(namespace, agent_id):
        raise HTTPException(status_code=403, detail="Agent may access only its own memory namespace")


def require_owner(x_owner_api_key: str = Header(default="", alias="X-Owner-API-Key")) -> str:
    configured = _secret("GARCAR_OWNER_API_KEY")
    if len(configured) < 32 or len(x_owner_api_key) < 32 or not hmac.compare_digest(
        hashlib.sha256(x_owner_api_key.encode()).digest(),
        hashlib.sha256(configured.encode()).digest(),
    ):
        raise HTTPException(status_code=403, detail="Independent owner authorization required")
    return os.getenv("GARCAR_OWNER_ID", "owner")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _audit(cur: psycopg.Cursor, proposal_id: str | None, event_type: str, actor: str, data: dict[str, Any]) -> None:
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (734_991_202_610_32,))
    cur.execute("SELECT event_hash FROM enterprise_audit_events ORDER BY event_id DESC LIMIT 1")
    previous = cur.fetchone()
    previous_hash = previous["event_hash"] if previous else ""
    digest = hashlib.sha256(previous_hash.encode() + _canonical({
        "proposal_id": proposal_id, "event_type": event_type, "actor_id": actor, "event_data": data
    })).hexdigest()
    cur.execute("""
        INSERT INTO enterprise_audit_events
          (proposal_id,event_type,actor_id,event_data,previous_event_hash,event_hash)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (proposal_id, event_type, actor, Jsonb(data), previous_hash or None, digest))


class ProposalRequest(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    agent_id: str = Field(min_length=1, max_length=64)
    layer: str = Field(min_length=1, max_length=32)
    target_action: str = Field(min_length=1, max_length=128)
    parameters: dict[str, Any]
    risk_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    requires_hitl: bool = True


class EvaluationRequest(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=64)
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    note: str = Field(default="", max_length=2000)


class VerificationRequest(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=64)
    authorization_token: str = Field(min_length=32, max_length=256)
    executor_id: str = Field(min_length=1, max_length=128)
    receipt: dict[str, Any]


class MemoryStoreRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=100000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] = Field(min_length=1536, max_length=1536)


class VectorQueryRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=64)
    query_embedding: list[float] = Field(min_length=1536, max_length=1536)
    match_threshold: float = Field(default=0.75, ge=0, le=1)
    limit: int = Field(default=5, ge=1, le=50)


@router.get("/governance/health")
def governance_health(_: str = Depends(require_agent)) -> dict[str, str]:
    with db_connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "database": "connected"}


@router.post("/governance/propose", status_code=202)
def submit_proposal(payload: ProposalRequest, actor: str = Depends(require_agent)) -> dict[str, str]:
    if not hmac.compare_digest(payload.agent_id, actor):
        raise HTTPException(status_code=403, detail="Proposal agent_id must match the authenticated agent")
    body = payload.model_dump()
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    with db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO enterprise_proposals
                      (proposal_id,agent_id,layer,target_action,parameters,risk_score,requires_hitl,status,payload_sha256)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'PENDING_EVALUATION',%s)
                    ON CONFLICT (proposal_id) DO NOTHING
                    RETURNING proposal_id
                """, (payload.proposal_id,payload.agent_id,payload.layer,payload.target_action,
                      Jsonb(payload.parameters),payload.risk_score,payload.requires_hitl,digest))
                inserted = cur.fetchone()
                if not inserted:
                    cur.execute("SELECT payload_sha256,status FROM enterprise_proposals WHERE proposal_id=%s FOR UPDATE",
                                (payload.proposal_id,))
                    existing = cur.fetchone()
                    if not existing or existing["payload_sha256"] != digest:
                        raise HTTPException(status_code=409, detail="Proposal ID already exists with different content")
                    return {"proposal_id": payload.proposal_id, "status": existing["status"], "idempotent": "true"}
                _audit(cur, payload.proposal_id, "PROPOSAL_SUBMITTED", actor, {"payload_sha256": digest})
    return {"proposal_id": payload.proposal_id, "status": "PENDING_EVALUATION", "idempotent": "false"}


@router.post("/governance/evaluate")
def evaluate_proposal(payload: EvaluationRequest, owner: str = Depends(require_owner)) -> dict[str, str]:
    with db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM enterprise_proposals WHERE proposal_id=%s FOR UPDATE", (payload.proposal_id,))
                proposal = cur.fetchone()
                if not proposal:
                    raise HTTPException(status_code=404, detail="Proposal not found")
                if proposal["status"] not in ("PENDING_EVALUATION", "PENDING_OWNER_HITL"):
                    raise HTTPException(status_code=409, detail=f"Proposal cannot be evaluated from {proposal['status']}")
                if payload.decision == "REJECTED":
                    cur.execute("UPDATE enterprise_proposals SET status='REJECTED',updated_at=now() WHERE proposal_id=%s",
                                (payload.proposal_id,))
                    cur.execute("""INSERT INTO enterprise_approvals(proposal_id,approver_id,decision,note)
                                   VALUES (%s,%s,'REJECTED',%s)""", (payload.proposal_id,owner,payload.note))
                    _audit(cur,payload.proposal_id,"PROPOSAL_REJECTED",owner,{"note":payload.note})
                    return {"proposal_id":payload.proposal_id,"status":"REJECTED"}
                passed, reason = evaluate_policy(proposal["layer"], proposal["parameters"], float(proposal["risk_score"]))
                if not passed and reason != "RISK_REQUIRES_MANUAL_REVIEW":
                    cur.execute("UPDATE enterprise_proposals SET status='REJECTED_POLICY_VIOLATION',updated_at=now() WHERE proposal_id=%s",
                                (payload.proposal_id,))
                    _audit(cur,payload.proposal_id,"POLICY_REJECTED",owner,{"reason":reason})
                    return {"proposal_id":payload.proposal_id,"status":"REJECTED_POLICY_VIOLATION","reason":reason}
                if reason == "RISK_REQUIRES_MANUAL_REVIEW" and len(payload.note.strip()) < 20:
                    raise HTTPException(status_code=422, detail="High-risk approval requires an owner justification of at least 20 characters")
                cur.execute("""INSERT INTO enterprise_approvals(proposal_id,approver_id,decision,note)
                               VALUES (%s,%s,'APPROVED',%s)""", (payload.proposal_id,owner,payload.note))
                token = secrets.token_urlsafe(36)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                expires = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
                cur.execute("""
                    UPDATE enterprise_proposals
                    SET status='APPROVED',authorization_token_hash=%s,authorization_expires_at=%s,
                        authorization_consumed_at=NULL,updated_at=now()
                    WHERE proposal_id=%s
                """, (token_hash,expires,payload.proposal_id))
                _audit(cur,payload.proposal_id,"PROPOSAL_APPROVED",owner,{"expires_at":expires.isoformat(),"manual_risk_override":reason == "RISK_REQUIRES_MANUAL_REVIEW","approval_note":payload.note})
    return {"proposal_id":payload.proposal_id,"status":"APPROVED","authorization_token":token,
            "expires_at":expires.isoformat()}


@router.post("/governance/verify")
def verify_execution(payload: VerificationRequest, actor: str = Depends(require_agent),
                     x_execution_signature: str = Header(default="", alias="X-Execution-Signature")) -> dict[str, Any]:
    if execution_is_blocked():
        raise HTTPException(status_code=503, detail="Emergency kill switch active; execution verification halted")
    if payload.receipt.get("success") is not True:
        raise HTTPException(status_code=422, detail="Receipt must explicitly attest success=true")
    signing_key = _secret("GARCAR_EXECUTION_SIGNING_KEY")
    if len(signing_key) < 32:
        raise HTTPException(status_code=503, detail="Execution receipt verification is not configured")
    signed_body = _canonical({"proposal_id":payload.proposal_id,"executor_id":payload.executor_id,"receipt":payload.receipt})
    expected = hmac.new(signing_key.encode(), signed_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_execution_signature):
        raise HTTPException(status_code=403, detail="Execution receipt signature invalid")
    receipt_hash = hashlib.sha256(signed_body).hexdigest()
    token_hash = hashlib.sha256(payload.authorization_token.encode()).hexdigest()
    with db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM enterprise_proposals WHERE proposal_id=%s FOR UPDATE", (payload.proposal_id,))
                proposal = cur.fetchone()
                if not proposal or proposal["status"] != "APPROVED":
                    raise HTTPException(status_code=409, detail="Proposal is not in an executable approved state")
                if not hmac.compare_digest(proposal["authorization_token_hash"] or "", token_hash):
                    raise HTTPException(status_code=403, detail="Invalid authorization token")
                if proposal["authorization_consumed_at"] is not None:
                    raise HTTPException(status_code=409, detail="Authorization token already consumed")
                if proposal["authorization_expires_at"] <= datetime.now(timezone.utc):
                    raise HTTPException(status_code=403, detail="Authorization token expired")
                cur.execute("""UPDATE enterprise_proposals
                    SET status='EXECUTED_AND_VERIFIED',receipt=%s,authorization_consumed_at=now(),updated_at=now()
                    WHERE proposal_id=%s""", (Jsonb(payload.receipt),payload.proposal_id))
                cur.execute("""INSERT INTO enterprise_execution_events
                    (proposal_id,event_type,executor_id,receipt,receipt_sha256)
                    VALUES (%s,'EXECUTION_VERIFIED',%s,%s,%s)""",
                    (payload.proposal_id,payload.executor_id,Jsonb(payload.receipt),receipt_hash))
                _audit(cur,payload.proposal_id,"EXECUTION_VERIFIED",actor,
                       {"executor_id":payload.executor_id,"receipt_sha256":receipt_hash})
    return {"proposal_id":payload.proposal_id,"evidence_logged":True,"final_status":"EXECUTED_AND_VERIFIED"}


@router.post("/memory/store", status_code=201)
def store_memory(payload: MemoryStoreRequest, actor: str = Depends(require_agent)) -> dict[str, Any]:
    _require_owned_namespace(payload.namespace, actor)
    if not all(math.isfinite(value) for value in payload.embedding):
        raise HTTPException(status_code=422, detail="Embedding values must be finite")
    with db_connection() as conn:
        with conn.transaction():
            row = conn.execute("""
                INSERT INTO enterprise_vector_memory(namespace,content,metadata,embedding)
                VALUES (%s,%s,%s,%s) RETURNING id,created_at
            """, (payload.namespace,payload.content,Jsonb(payload.metadata),Vector(payload.embedding))).fetchone()
    return {"status":"stored","id":row["id"],"created_at":row["created_at"].isoformat()}


@router.post("/memory/search")
def search_memory(payload: VectorQueryRequest, actor: str = Depends(require_agent)) -> dict[str, Any]:
    _require_owned_namespace(payload.namespace, actor)
    if not all(math.isfinite(value) for value in payload.query_embedding):
        raise HTTPException(status_code=422, detail="Query embedding values must be finite")
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT id,namespace,content,metadata,1-(embedding <=> %s) AS similarity
            FROM enterprise_vector_memory
            WHERE namespace=%s AND 1-(embedding <=> %s) >= %s
            ORDER BY embedding <=> %s
            LIMIT %s
        """, (Vector(payload.query_embedding),payload.namespace,Vector(payload.query_embedding),
              payload.match_threshold,Vector(payload.query_embedding),payload.limit)).fetchall()
    return {"matches":rows}


@router.get("/governance/execution-allowed")
def execution_allowed(_: str = Depends(require_agent)) -> dict[str, bool]:
    """Read the persistent stop state before an executor performs side effects."""
    return {"execution_allowed": not execution_is_blocked()}


@router.post("/governance/kill-switch")
def set_kill_switch(enabled: bool, owner: str = Depends(require_owner)) -> dict[str, Any]:
    with db_connection() as conn:
        with conn.transaction():
            conn.execute("""
                INSERT INTO enterprise_control_state(control_name,enabled,updated_by,updated_at)
                VALUES ('execution_kill_switch',%s,%s,now())
                ON CONFLICT(control_name) DO UPDATE SET enabled=EXCLUDED.enabled,
                    updated_by=EXCLUDED.updated_by,updated_at=now()
            """, (enabled,owner))
            with conn.cursor() as cur:
                _audit(cur,None,"KILL_SWITCH_CHANGED",owner,{"enabled":enabled})
    return {"kill_switch_active":enabled}


def execution_is_blocked() -> bool:
    with db_connection() as conn:
        row = conn.execute("SELECT enabled FROM enterprise_control_state WHERE control_name='execution_kill_switch'").fetchone()
    return bool(row and row["enabled"])
