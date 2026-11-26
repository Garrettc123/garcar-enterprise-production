"""Strictly authenticated payment handoff, not an independent Stripe revenue source."""
from __future__ import annotations
import hmac
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .contracts import BadHandoff, parse_handoff, MAX_BODY_BYTES
from .db import PayloadConflict, check_ready, record_receipt

app = FastAPI(title="Garcar fulfillment intake", docs_url=None, redoc_url=None, openapi_url=None)

@app.get("/health")
def health():
    return {"status": "alive", "fulfillment_proven": False}

@app.get("/readyz")
def ready():
    if len(os.environ.get("FULFILLMENT_WEBHOOK_TOKEN", "")) < 32:
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "receiver_auth_unavailable"})
    try:
        if check_ready():
            return {"status": "ready", "fulfillment_proven": False}
    except Exception:
        pass
    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "database_unavailable"})

@app.post("/v1/fulfillment")
@app.post("/api/fulfillment")
async def accept_handoff(request: Request):
    token = os.environ.get("FULFILLMENT_WEBHOOK_TOKEN", "")
    if len(token) < 32:
        return JSONResponse(status_code=503, content={"error": "receiver_not_configured"})
    authorization = request.headers.get("authorization", "")
    if not hmac.compare_digest(authorization, "Bearer " + token):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return JSONResponse(status_code=415, content={"error": "unsupported_media_type"})
    if int(request.headers.get("content-length", "0") or 0) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"error": "payload_too_large"})
    body = await request.body()
    try:
        message, digest = parse_handoff(body, request.headers.get("idempotency-key", ""))
    except BadHandoff as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    try:
        inserted = record_receipt(message, digest)
    except PayloadConflict:
        return JSONResponse(status_code=409, content={"error": "idempotency_conflict"})
    except Exception:
        return JSONResponse(status_code=503, content={"error": "persistence_unavailable"})
    return JSONResponse(status_code=202 if inserted else 200, content={
        "accepted": True,
        "duplicate": not inserted,
        "processing_status": "RECEIVED_UNFULFILLED",
        "payment_reference": message["payment_reference"],
        "revenue_verification": "upstream_stripe_reconciliation_required",
    })
