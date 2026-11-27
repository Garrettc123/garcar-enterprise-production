"""Stripe inbound signed webhook for REOS-tagged LIVE payment-intent receipts only.

Never initiates a charge. Counts successful payment events as receipts, not as payouts,
profit or automatically fulfilled services. A checkout/payment connector is required
elsewhere before this receiver sees events.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import sqlite3
import time
from decimal import Decimal
from typing import Any
from .store import CaseStore, Conflict, stamp

MAX_BODY_BYTES = 512_000

def validate_signature(body: bytes, header: str, secret: str, now: int | None = None) -> None:
    if not secret.startswith("whsec_") or len(secret) < 15:
        raise ValueError("Stripe webhook signing secret unavailable")
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("Stripe payload too large")
    parts: dict[str, list[str]] = {}
    for part in header.split(","):
        k, sep, v = part.strip().partition("=")
        if sep: parts.setdefault(k, []).append(v)
    timestamps = parts.get("t", [])
    if len(timestamps) != 1 or not timestamps[0].isdigit():
        raise ValueError("Invalid Stripe signature timestamp")
    ts = int(timestamps[0]); current = now if now is not None else int(time.time())
    if abs(current - ts) > 300:
        raise ValueError("Stripe signature timestamp outside tolerance")
    message = f"{ts}.".encode() + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(candidate, expected) for candidate in parts.get("v1", [])):
        raise ValueError("Invalid Stripe signature")

class ReceiptStore(CaseStore):
    def initialize(self):
        super().initialize()
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS verified_stripe_receipts (
                    event_id TEXT PRIMARY KEY, payment_intent_id TEXT UNIQUE NOT NULL,
                    case_id TEXT, amount_received_cents INTEGER NOT NULL,
                    currency TEXT NOT NULL, event_created INTEGER NOT NULL,
                    received_at TEXT NOT NULL
                );
            """)

    def ingest_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
            raise ValueError("Malformed Stripe event")
        obj = event["data"].get("object", {})
        if event.get("type") != "payment_intent.succeeded" or event.get("livemode") is not True:
            return {"accepted": False, "reason": "Only live successful payment_intent events accepted"}
        if not isinstance(obj, dict) or obj.get("object") != "payment_intent":
            raise ValueError("Malformed Stripe payment_intent")
        metadata = obj.get("metadata") or {}
        if not isinstance(metadata, dict) or metadata.get("reos_product") != "real_estate_intelligence":
            return {"accepted": False, "reason": "Payment intent not tagged as REOS"}
        amount = obj.get("amount_received")
        if type(amount) is not int or not 0 < amount <= 100_000_000_00:
            raise ValueError("Invalid captured amount")
        eid, pid = event.get("id"), obj.get("id")
        if not (isinstance(eid, str) and eid.startswith("evt_") and isinstance(pid, str) and pid.startswith("pi_")):
            raise ValueError("Invalid Stripe identifiers")
        case_id = metadata.get("reos_case_id") or None
        if case_id is not None: self.get_case(case_id)
        currency = obj.get("currency")
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
            raise ValueError("Invalid currency")
        timestamp = event.get("created")
        if type(timestamp) is not int or timestamp < 0:
            raise ValueError("Invalid event creation timestamp")
        with self.connection(True) as db:
            if db.execute("SELECT event_id FROM verified_stripe_receipts WHERE event_id=? OR payment_intent_id=?", (eid, pid)).fetchone():
                return {"accepted": True, "duplicate": True}
            db.execute("INSERT INTO verified_stripe_receipts VALUES(?,?,?,?,?,?,?)",
                       (eid, pid, case_id, amount, currency.lower(), timestamp, stamp()))
            self._audit(db, "stripe.payment_receipt_verified", case_id or pid,
                        {"event_id": eid, "payment_intent_id": pid, "amount_cents": amount,
                         "currency": currency.lower(), "case_id": case_id})
        return {"accepted": True, "duplicate": False, "event_id": eid}

    def revenue_summary(self) -> dict[str, Any]:
        with self.connection() as db:
            rows = db.execute("SELECT currency,COUNT(*) events,SUM(amount_received_cents) cents "
                              "FROM verified_stripe_receipts GROUP BY currency").fetchall()
        return {"verified_signed_live_receipts": [{"currency": r["currency"], "payment_events": r["events"],
                "gross_received": str((Decimal(r["cents"]) / 100).quantize(Decimal("0.01")))} for r in rows],
                "account_net_payouts_verified": False, "refunds_verified": False,
                "warning": "Signed event verification does not prove transfer to bank, final net profit or absence of refunds."}
