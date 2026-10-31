from typing import Any
from .ledger import seal_record

def record_verified_payout(event: dict[str, Any], *, bucket: str, region: str, retention_days: int) -> dict[str, str]:
    if event.get("type") != "payout.paid":
        return {"result": "ignored"}
    event_id = event.get("id")
    obj = event.get("data", {}).get("object", {})
    if not event_id or not obj.get("id") or obj.get("status") != "paid":
        raise ValueError("Verified payout event requires event ID, payout ID and paid status")
    amount, currency = obj.get("amount"), obj.get("currency")
    if not isinstance(amount, int) or amount < 0 or not isinstance(currency, str) or len(currency) != 3:
        raise ValueError("Payout amount or currency is invalid")
    record = {
        "event_id": event_id, "payout_id": obj["id"], "amount_minor": amount,
        "currency": currency.lower(), "status": "paid", "event_type": "STRIPE_PAYOUT_PAID",
    }
    return seal_record(record, bucket, region, retention_days)
