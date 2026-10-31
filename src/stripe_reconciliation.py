"""Stripe webhook signature validation and evidence-only reconciliation."""
from __future__ import annotations

from typing import Any

import stripe
from stripe import SignatureVerificationError
from fastapi import HTTPException


def verify_stripe_event(payload: bytes, signature: str | None, webhook_secret: str) -> dict[str, Any]:
    if not signature or not webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook verification is not configured")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature or payload") from exc
    # Whitelist only identifiers and lifecycle metadata. Never retain full payment payloads.
    data_object = event.get("data", {}).get("object", {}) or {}
    return {
        "event_id": event["id"],
        "event_type": event["type"],
        "created": event.get("created"),
        "livemode": bool(event.get("livemode", False)),
        "object_id": data_object.get("id"),
        "object_status": data_object.get("status"),
        "reconciliation_state": "RECORDED_NOT_ACTIONED",
        "funds_moved": False,
    }
