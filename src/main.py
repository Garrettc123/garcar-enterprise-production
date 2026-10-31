import hashlib
import hmac
import json
import logging
import time
from contextlib import asynccontextmanager

import hvac
import stripe
from pydantic import ValidationError
from stripe import SignatureVerificationError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import settings
from .ledger import LedgerError, seal_record
from .orchestrator import PermitInput, evaluate_permit
from .payouts import record_verified_payout

log = logging.getLogger("garcar")
cfg = settings()
vault_data: dict = {}


def _vault_client() -> hvac.Client:
    client = hvac.Client(url=cfg.vault_addr)
    if cfg.vault_auth_method == "token":
        if not cfg.vault_token:
            raise RuntimeError("VAULT_TOKEN is required for token authentication")
        client.token = cfg.vault_token
    elif cfg.vault_auth_method == "aws_iam":
        if not cfg.vault_aws_role:
            raise RuntimeError("VAULT_AWS_ROLE is required for AWS IAM authentication")
        client.auth.aws.iam_login(role=cfg.vault_aws_role, mount_point="aws")
    else:
        raise RuntimeError("Unsupported Vault authentication method")
    if not client.is_authenticated():
        raise RuntimeError("Vault authentication failed")
    return client


def webhook_secret() -> str:
    secret = vault_data.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret and cfg.environment != "production":
        secret = cfg.stripe_webhook_secret
    return secret


def permit_ingest_secret() -> str:
    secret = vault_data.get("PERMIT_INGEST_HMAC_SECRET", "")
    if not secret and cfg.environment != "production":
        secret = cfg.permit_ingest_hmac_secret
    return secret


def verify_permit_signature(
    payload: bytes,
    timestamp_header: str,
    signature_header: str,
    secret: str,
    *,
    now: int | None = None,
) -> bool:
    if len(secret.encode("utf-8")) < 32 or not timestamp_header or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    try:
        timestamp = int(timestamp_header)
    except (TypeError, ValueError):
        return False
    current_time = int(time.time()) if now is None else now
    if abs(current_time - timestamp) > cfg.permit_ingest_tolerance_seconds:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        str(timestamp).encode("ascii") + b"." + payload,
        hashlib.sha256,
    ).hexdigest()
    supplied = signature_header.removeprefix("sha256=")
    if len(supplied) != 64:
        return False
    return hmac.compare_digest(expected, supplied)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault_data
    if cfg.require_vault:
        client = _vault_client()
        response = client.secrets.kv.v2.read_secret_version(
            mount_point=cfg.vault_mount, path=cfg.vault_path
        )
        vault_data = response["data"]["data"]
        if cfg.environment == "production":
            required = ("STRIPE_WEBHOOK_SECRET", "PERMIT_INGEST_HMAC_SECRET")
            missing = [name for name in required if not vault_data.get(name)]
            if missing:
                raise RuntimeError(
                    "Required production webhook secrets are missing from Vault: "
                    + ", ".join(missing)
                )
            permit_secret = vault_data["PERMIT_INGEST_HMAC_SECRET"]
            if not isinstance(permit_secret, str) or len(permit_secret.encode("utf-8")) < 32:
                raise RuntimeError(
                    "PERMIT_INGEST_HMAC_SECRET must contain at least 32 UTF-8 bytes"
                )
    else:
        if cfg.environment == "production":
            raise RuntimeError("Vault cannot be disabled in production")
        vault_data = {}
    yield
    vault_data = {}


app = FastAPI(
    title="Garcar Enterprise Immutable Wealth Machine",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "environment": cfg.environment,
        "execution_mode": "guarded",
    }


@app.post("/webhook/permits/dfw")
async def ingest_permit(request: Request):
    secret = permit_ingest_secret()
    if not secret:
        raise HTTPException(
            status_code=503, detail="Permit webhook authentication is not configured"
        )

    payload = await request.body()
    if len(payload) > 1_048_576:
        raise HTTPException(status_code=413, detail="Permit payload exceeds 1 MiB")

    timestamp = request.headers.get("x-garcar-timestamp", "")
    signature = request.headers.get("x-garcar-signature", "")
    if not verify_permit_signature(payload, timestamp, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid or expired permit signature")

    try:
        permit = PermitInput.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid permit payload") from exc

    record = {"event_type": "PERMIT_INGESTED", **permit.model_dump()}
    try:
        ledger = seal_record(
            record, cfg.s3_ledger_bucket, cfg.aws_region, cfg.ledger_retention_days
        )
    except LedgerError as exc:
        raise HTTPException(
            status_code=503, detail="Ledger unavailable; request not processed"
        ) from exc
    return {
        "status": "recorded",
        "ledger": ledger,
        "decision": evaluate_permit(permit),
    }


@app.post("/webhook/payouts")
async def stripe_payout_webhook(request: Request):
    secret = webhook_secret()
    if not secret:
        raise HTTPException(
            status_code=503, detail="Stripe webhook verification is not configured"
        )
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
        result = record_verified_payout(
            event,
            bucket=cfg.s3_ledger_bucket,
            region=cfg.aws_region,
            retention_days=cfg.ledger_retention_days,
        )
    except (ValueError, SignatureVerificationError) as exc:
        raise HTTPException(
            status_code=400, detail="Invalid webhook payload or signature"
        ) from exc
    except LedgerError as exc:
        raise HTTPException(
            status_code=503, detail="Ledger unavailable; webhook not acknowledged"
        ) from exc
    return JSONResponse({"status": "received", "ledger": result})
