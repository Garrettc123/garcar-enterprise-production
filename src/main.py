"""Guarded permit-ingestion API for Garcar Enterprise.

This service records evidence and prepares review work. It never sends outreach,
approves a contractor, or initiates a payment.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import boto3
import hvac
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

APP_ENV = os.getenv("APP_ENV", "production")
VAULT_ADDR = os.getenv("VAULT_ADDR")
VAULT_ROLE_ID = os.getenv("VAULT_ROLE_ID")
VAULT_SECRET_ID = os.getenv("VAULT_SECRET_ID")
VAULT_KV_PATH = os.getenv("VAULT_KV_PATH", "garcar/production/keys")
VAULT_MOUNT = os.getenv("VAULT_MOUNT", "secret")
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN")
S3_BUCKET = os.getenv("S3_LEDGER_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

app = FastAPI(
    title="Garcar Enterprise Evidence Gateway",
    version="0.1.0",
    description="Evidence intake and review preparation; no autonomous external actions.",
)


class PermitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: UUID
    permit_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    municipality: str = Field(min_length=2, max_length=100)
    contractor_name: str = Field(min_length=1, max_length=200)
    property_address: str = Field(min_length=5, max_length=300)
    valuation: float = Field(ge=0, le=1_000_000_000)
    description: str = Field(default="", max_length=5000)
    filing_date: str = Field(min_length=8, max_length=40)

    @field_validator("municipality", "contractor_name", "property_address")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("Control characters are not allowed")
        return value


def _vault_client() -> hvac.Client:
    if not VAULT_ADDR or not VAULT_ROLE_ID or not VAULT_SECRET_ID:
        raise RuntimeError("Vault AppRole configuration is required; refusing fallback credentials")
    client = hvac.Client(url=VAULT_ADDR, timeout=5)
    auth = client.auth.approle.login(
        role_id=VAULT_ROLE_ID,
        secret_id=VAULT_SECRET_ID,
    )
    if not auth or not client.is_authenticated():
        raise RuntimeError("Vault authentication failed")
    return client


def load_runtime_config() -> dict[str, str]:
    """Load runtime configuration from Vault; fail closed in every environment."""
    client = _vault_client()
    response = client.secrets.kv.v2.read_secret_version(
        mount_point=VAULT_MOUNT,
        path=VAULT_KV_PATH,
    )
    values = response.get("data", {}).get("data", {})
    bucket = values.get("S3_LEDGER_BUCKET") or S3_BUCKET
    if not bucket:
        raise RuntimeError("S3_LEDGER_BUCKET is missing from Vault/configuration")
    return {"S3_LEDGER_BUCKET": bucket}


def require_api_auth(authorization: str | None = Header(default=None)) -> None:
    if not API_BEARER_TOKEN:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    expected = f"Bearer {API_BEARER_TOKEN}"
    if authorization is None or not __import__("hmac").compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _s3_client():
    # Uses the AWS SDK default credential chain (e.g. task role or OIDC role).
    # Static AWS access keys are intentionally not accepted from application config.
    return boto3.client("s3", region_name=AWS_REGION)


def verify_worm_configuration(s3: Any, bucket: str) -> dict[str, Any]:
    try:
        lock = s3.get_object_lock_configuration(Bucket=bucket)
        retention = lock.get("ObjectLockConfiguration", {}).get("Rule", {}).get("DefaultRetention", {})
        versioning = s3.get_bucket_versioning(Bucket=bucket)
    except ClientError as exc:
        raise RuntimeError("Unable to verify S3 Object Lock configuration") from exc

    if lock.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") != "Enabled":
        raise RuntimeError("S3 Object Lock is not enabled")
    if versioning.get("Status") != "Enabled":
        raise RuntimeError("S3 bucket versioning is not enabled")
    if retention.get("Mode") != "COMPLIANCE":
        raise RuntimeError("Default retention must be COMPLIANCE")
    if not retention.get("Days") and not retention.get("Years"):
        raise RuntimeError("Default compliance retention period is missing")
    return {"mode": retention["Mode"], "days": retention.get("Days"), "years": retention.get("Years")}


def seal_event(payload: PermitPayload, config: dict[str, str]) -> str:
    s3 = _s3_client()
    bucket = config["S3_LEDGER_BUCKET"]
    retention = verify_worm_configuration(s3, bucket)
    record = {
        "schema_version": 1,
        "event_id": str(payload.event_id),
        "event_type": "PERMIT_INGESTED",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "permit": payload.model_dump(mode="json"),
        "retention_verified": retention,
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    body = json.dumps({**record, "sha256": digest}, sort_keys=True, indent=2).encode()
    key = f"evidence/permit-events/{payload.event_id}.json"
    try:
        write_result = s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            Metadata={"sha256": digest, "event-id": str(payload.event_id)},
            IfNoneMatch="*",
        )
        version_id = write_result.get("VersionId")
        if not version_id:
            raise RuntimeError("S3 did not return a version ID; ledger write is not accepted")
        stored = s3.head_object(Bucket=bucket, Key=key, VersionId=version_id)
        if stored.get("ObjectLockMode") != "COMPLIANCE" or not stored.get("ObjectLockRetainUntilDate"):
            raise RuntimeError("Stored object does not have verified COMPLIANCE retention")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"PreconditionFailed", "412", "ConditionalRequestConflict"}:
            # Duplicate event IDs are not silently overwritten.
            raise HTTPException(status_code=409, detail="event_id already exists") from exc
        raise RuntimeError("Evidence ledger write failed") from exc
    return digest


def prepare_review(payload: PermitPayload, digest: str) -> dict[str, Any]:
    # No fabricated ratings, inferred history, automatic approval, or outreach.
    return {
        "status": "HUMAN_REVIEW_REQUIRED",
        "permit_id": payload.permit_id,
        "ledger_hash": digest,
        "contractor_rating": None,
        "past_projects_count": None,
        "evidence_status": "NOT_ENRICHED",
        "approval": "NOT_GRANTED",
        "outreach": "NOT_SENT",
        "next_action": "Verify source records and obtain explicit owner approval.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "evidence-intake-only"}


@app.post("/webhook/permits/dfw", dependencies=[Depends(require_api_auth)])
async def ingest_permit(permit: PermitPayload) -> dict[str, Any]:
    try:
        config = load_runtime_config()
        digest = seal_event(permit, config)
    except HTTPException:
        raise
    except Exception as exc:
        # Do not leak credentials, Vault responses, bucket names, or provider internals.
        raise HTTPException(status_code=503, detail="Evidence intake unavailable; no approval or outreach occurred") from exc
    return prepare_review(permit, digest)
