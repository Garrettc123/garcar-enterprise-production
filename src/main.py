import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import hvac, stripe
from .config import settings
from .ledger import seal_record, LedgerError
from .orchestrator import PermitInput, evaluate_permit
from .payouts import record_verified_payout

log = logging.getLogger("garcar")
cfg = settings()
vault_data: dict = {}

def webhook_secret() -> str:
    # Production signing secret is sourced from Vault, never a committed default.
    secret = vault_data.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret and cfg.environment != "production":
        secret = cfg.stripe_webhook_secret
    return secret

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault_data
    if cfg.require_vault:
        if not cfg.vault_addr or not cfg.vault_token:
            raise RuntimeError("Vault authentication is required; no development-token fallback is permitted")
        client = hvac.Client(url=cfg.vault_addr, token=cfg.vault_token)
        if not client.is_authenticated():
            raise RuntimeError("Vault authentication failed")
        response = client.secrets.kv.v2.read_secret_version(mount_point=cfg.vault_mount, path=cfg.vault_path)
        vault_data = response["data"]["data"]
    else:
        vault_data = {}
    yield
    vault_data = {}

app = FastAPI(title="Garcar Enterprise Immutable Wealth Machine", version="0.1.0", lifespan=lifespan)

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
    decision = evaluate_permit(permit)
    return {"status": "recorded", "ledger": ledger, "decision": decision}

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
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload or signature") from exc
    except LedgerError as exc:
        raise HTTPException(status_code=503, detail="Ledger unavailable; webhook not acknowledged") from exc
    return JSONResponse({"status": "received", "ledger": result})
