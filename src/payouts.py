from typing import Any
from .ledger import seal_record

def record_verified_payout(event: dict[str, Any], *, bucket: str, region: str, retention_days: int) -> dict[str, str]:
    if event.get("type") != "payout.paid":
        return {"result": "ignored"}
    obj = event.get("data", {}).get("object", {})
    if not obj.get("id") or obj.get("status") != "paid":
        raise ValueError("Payout event is missing a verified paid object")
    record = {
        "event_id": event.get("id"),
        "payout_id": obj["id"],
        "amount_minor": obj.get("amount"),
        "currency": obj.get("currency"),
        "status": obj["status"],
        "event_type": "STRIPE_PAYOUT_PAID",
    }
    return seal_record(record, bucket, region, retention_days)
