"""Validate authenticated Garcar payment handoffs; no synthetic revenue records."""
from __future__ import annotations
import hashlib
import json
import re

REFERENCE = re.compile(r"^[a-zA-Z0-9._:-]{1,160}$")
SKU = re.compile(r"^[a-zA-Z0-9._:-]{1,100}$")
MAX_BODY_BYTES = 32768

class BadHandoff(ValueError):
    pass

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BadHandoff("duplicate JSON key")
        result[key] = value
    return result

def parse_handoff(body: bytes, idempotency_key: str) -> tuple[dict, str]:
    if not body or len(body) > MAX_BODY_BYTES:
        raise BadHandoff("invalid payload length")
    try:
        message = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadHandoff("malformed JSON") from exc
    if not isinstance(message, dict):
        raise BadHandoff("expected JSON object")
    if message.get("event") != "garcar.payment.received":
        raise BadHandoff("unsupported event")
    reference = message.get("payment_reference")
    sku = message.get("sku")
    amount = message.get("amount_minor")
    currency = message.get("currency")
    if not isinstance(reference, str) or not REFERENCE.fullmatch(reference):
        raise BadHandoff("invalid payment reference")
    if not isinstance(idempotency_key, str) or idempotency_key != reference:
        raise BadHandoff("idempotency mismatch")
    if not isinstance(sku, str) or not SKU.fullmatch(sku):
        raise BadHandoff("invalid SKU")
    if type(amount) is not int or not 1 <= amount <= 1_000_000_000:
        raise BadHandoff("invalid payment amount")
    if currency != "usd":
        raise BadHandoff("unsupported payment currency")
    fields = {"offer_name": 180, "customer_email": 254, "created_at": 80}
    for key, limit in fields.items():
        if not isinstance(message.get(key, ""), str) or len(message.get(key, "")) > limit:
            raise BadHandoff("invalid " + key)
    hours = message.get("fulfill_hours")
    if hours is not None and (type(hours) is not int or not 0 <= hours <= 720):
        raise BadHandoff("invalid fulfillment window")
    normalized = {
        "event": "garcar.payment.received",
        "payment_reference": reference,
        "idempotency_key": reference,
        "sku": sku,
        "amount_minor": amount,
        "currency": currency,
        "offer_name": message.get("offer_name", ""),
        "customer_email": message.get("customer_email", ""),
        "created_at": message.get("created_at", ""),
        "fulfill_hours": hours,
    }
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return normalized, hashlib.sha256(payload).hexdigest()
