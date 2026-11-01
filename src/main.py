"""Guarded evidence-ingress API for Garcar Enterprise.

The service records evidence and prepares review work. It never sends outreach,
approves a contractor, or initiates a payment.
"""
from __future__ import annotations

import base64
import hmac
import os
from typing import Any
from uuid import UUID

import boto3
import hvac
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.evidence import build_contractor_profile
from src.hash_chain import append_event
from src.rhns_policy import PolicyContext, evaluate_rhns_policy

APP_ENV = os.getenv("APP_ENV", "production")
VAULT_ADDR = os.getenv("VAULT_ADDR")
VAULT_ROLE_ID = os.getenv("VAULT_ROLE_ID")
VAULT_SECRET_ID = os.getenv("VAULT_SECRET_ID")
VAULT_KV_PATH = os.getenv("VAULT_KV_PATH", "garcar/production/keys")
VAULT_MOUNT = os.getenv("VAULT_MOUNT", "secret")
S3_BUCKET = os.getenv("S3_LEDGER_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

app = FastAPI(
    title="Garcar Enterprise Evidence Gateway",
    version="0.2.0",
    description="Evidence intake, payout reconciliation, and review preparation; no autonomous external actions.",
)


class PermitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: UUID
    permit_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    municipality: str = Field(min_length=2, max_length=100)
    contractor_name: str = Field(min_length=1, max_length=200)
    property_address: str = Field(min_length=5, max_length=300)
    valuation: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
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
    auth = client.auth.approle.login(role_id=VAULT_ROLE_ID, secret_id=VAULT_SECRET_ID)
    if not auth or not client.is_authenticated():
        raise RuntimeError("Vault authentication failed")
    return client


def validate_runtime_config(values: dict[str, Any]) -> dict[str, str]:
    """Validate Vault KV values without logging or returning secret material to callers."""
    config = {
        "S3_LEDGER_BUCKET": values.get("S3_LEDGER_BUCKET") or S3_BUCKET or "",
        "OWNER_APPROVAL_PUBLIC_KEY": values.get("OWNER_APPROVAL_PUBLIC_KEY") or "",
        "STRIPE_WEBHOOK_SECRET": values.get("STRIPE_WEBHOOK_SECRET") or "",
        "API_BEARER_TOKEN": values.get("API_BEARER_TOKEN") or "",
    }
    missing = [name for name, value in config.items() if not isinstance(value, str) or not value.strip()]
    if missing:
        raise RuntimeError("Required Vault/runtime values are missing: " + ", ".join(missing))
    if len(config["API_BEARER_TOKEN"]) < 32:
        raise RuntimeError("API_BEARER_TOKEN must contain at least 32 characters")
    try:
        public_key = base64.b64decode(config["OWNER_APPROVAL_PUBLIC_KEY"], validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("OWNER_APPROVAL_PUBLIC_KEY must be base64-encoded Ed25519 public-key bytes") from exc
    if len(public_key) != 32:
        raise RuntimeError("OWNER_APPROVAL_PUBLIC_KEY must decode to exactly 32 bytes")
    if not config["STRIPE_WEBHOOK_SECRET"].startswith("whsec_"):
        raise RuntimeError("STRIPE_WEBHOOK_SECRET has an invalid format")
    return config


def load_runtime_config() -> dict[str, str]:
    """Load runtime configuration from Vault; fail closed in every environment."""
    client = _vault_client()
    response = client.secrets.kv.v2.read_secret_version(
        mount_point=VAULT_MOUNT,
        path=VAULT_KV_PATH,
    )
    values = response.get("data", {}).get("data", {})
    return validate_runtime_config(values)


def require_api_auth(authorization: str | None = Header(default=None)) -> None:
    try:
        expected_token = load_runtime_config().get("API_BEARER_TOKEN", "")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="API authentication service unavailable") from exc
    if not expected_token:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    expected = f"Bearer {expected_token}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
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

    try:
        public_access = s3.get_public_access_block(Bucket=bucket).get(
            "PublicAccessBlockConfiguration", {}
        )
        encryption_rules = s3.get_bucket_encryption(Bucket=bucket).get(
            "ServerSideEncryptionConfiguration", {}
        ).get("Rules", [])
    except ClientError as exc:
        raise RuntimeError("Unable to verify S3 public-access and encryption controls") from exc

    required_public_controls = (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    )
    if not all(public_access.get(control) is True for control in required_public_controls):
        raise RuntimeError("All four S3 Block Public Access settings must be enabled")
    algorithms = [
        rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm")
        for rule in encryption_rules
    ]
    if not algorithms or any(value != "AES256" for value in algorithms):
        raise RuntimeError(
            "S3 default server-side encryption must be AES256; KMS requires a separately reviewed runtime policy"
        )

    return {
        "mode": retention["Mode"],
        "days": retention.get("Days"),
        "years": retention.get("Years"),
        "public_access_blocked": True,
        "encryption": sorted(set(algorithms)),
    }


def seal_event(payload: PermitPayload, config: dict[str, str]) -> str:
    s3 = _s3_client()
    record = {
        "schema_version": 1,
        "event_id": str(payload.event_id),
        "event_type": "PERMIT_INGESTED",
        "permit": payload.model_dump(mode="json"),
    }
    return append_event(
        s3, config["S3_LEDGER_BUCKET"], str(payload.event_id), record,
        verify_worm_configuration,
    )


def prepare_review(payload: PermitPayload, digest: str) -> dict[str, Any]:
    profile = build_contractor_profile(payload.contractor_name)
    policy = evaluate_rhns_policy(
        PolicyContext(
            municipality=payload.municipality,
            valuation=payload.valuation,
            permit_source_verified=False,
            contractor_identity_verified=False,
            authority_verified=False,
            owner_approval_verified=False,
            evidence_refs=[str(item.source_uri) for item in profile.evidence],
        )
    )
    return {
        "status": policy["decision"],
        "permit_id": payload.permit_id,
        "ledger_hash": digest,
        "contractor_rating": profile.rating,
        "past_projects_count": profile.completed_project_count,
        "evidence_status": profile.evidence_state,
        "policy_reasons": policy["reasons"],
        "risk_score": policy["risk_score"],
        "approval": "NOT_GRANTED",
        "outreach": "NOT_SENT",
        "next_action": "Verify source records, budget authority, and obtain signed owner approval.",
    }


@app.get("/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health")
async def health() -> dict[str, Any]:
    # Readiness is only true when Vault and the immutable ledger are reachable.
    try:
        config = load_runtime_config()
        retention = verify_worm_configuration(_s3_client(), config["S3_LEDGER_BUCKET"])
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Required production dependencies are unavailable") from exc
    return {"status": "ready", "mode": "evidence-intake-only", "ledger_retention": retention}


@app.post("/webhook/permits/dfw", dependencies=[Depends(require_api_auth)])
async def ingest_permit(permit: PermitPayload) -> dict[str, Any]:
    try:
        config = load_runtime_config()
        digest = seal_event(permit, config)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Evidence intake unavailable; no approval or outreach occurred") from exc
    return prepare_review(permit, digest)


# Routes are imported after core definitions to avoid circular initialization.
from src.extended_routes import router as extended_router  # noqa: E402
app.include_router(extended_router)
