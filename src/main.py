import logging
import os
from contextlib import asynccontextmanager

import hvac
import stripe
from stripe import SignatureVerificationError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import settings
from .ledger import LedgerError, seal_record
from .orchestrator import PermitInput, evaluate_permit
from .payouts import record_verified_payout
from .governance.router import router as governance_router, configure_runtime_secrets

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault_data
    if cfg.require_vault:
        client = _vault_client()
        response = client.secrets.kv.v2.read_secret_version(mount_point=cfg.vault_mount, path=cfg.vault_path)
        vault_data = response["data"]["data"]
        configure_runtime_secrets(vault_data)
        if cfg.environment == "production":
            required = ["STRIPE_WEBHOOK_SECRET"]
            if os.getenv("ENABLE_GOVERNANCE_DB", "false").lower() == "true":
                required.extend(("GARCAR_AGENT_API_KEYS", "GARCAR_OWNER_API_KEY", "GARCAR_EXECUTION_SIGNING_KEY"))
            missing = [name for name in required if not vault_data.get(name)]
            if missing:
                raise RuntimeError("Required production secrets missing from Vault: " + ", ".join(missing))
    else:
        if cfg.environment == "production":
            raise RuntimeError("Vault cannot be disabled in production")
        vault_data = {}
        configure_runtime_secrets({})
    yield
    vault_data = {}

app = FastAPI(title="Garcar Enterprise Immutable Wealth Machine", version="0.3.0", lifespan=lifespan)

# Governance endpoints are opt-in; do not expose them when the database migration gate is disabled.
if os.getenv("ENABLE_GOVERNANCE_DB", "false").lower() == "true":
    app.include_router(governance_router)

@app.get("/health")
async def health():
    return {"status": "ok", "environment": cfg.environment, "execution_mode": "guarded"}

@app.post("/webhook/permits/dfw")
async def ingest_permit(permit: PermitInput):
    record = {"event_type": "PERMIT_INGESTED", **permit.model_dump()}
    try:
        ledger = seal_record(record, cfg.s3_ledger_bucket, cfg.aws_region, cfg.ledger_retention_days)
    except LedgerError as exc:
        raise HTTPException(status_code=503, detail="Ledger unavailable; request not processed") from exc
    return {"status": "recorded", "ledger": ledger, "decision": evaluate_permit(permit)}

@app.post("/webhook/payouts")
async def stripe_payout_webhook(request: Request):
    secret = webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Stripe webhook verification is not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
        result = record_verified_payout(event, bucket=cfg.s3_ledger_bucket, region=cfg.aws_region, retention_days=cfg.ledger_retention_days)
    except (ValueError, SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload or signature") from exc
    except LedgerError as exc:
        raise HTTPException(status_code=503, detail="Ledger unavailable; webhook not acknowledged") from exc
    return JSONResponse({"status": "received", "ledger": result})
