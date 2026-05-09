"""GAR-421: Revenue Allocation Rules
40% Owner Pay / 25% Ops / 20% Tax Reserve / 15% Reinvest
Trigger: Stripe payout webhook or manual call.
"""
import os
import stripe
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

ALLOCATION_RULES = {
    "owner_pay": 0.40,
    "operations": 0.25,
    "tax_reserve": 0.20,
    "reinvestment": 0.15,
}

# Bank account / Stripe Connect destination IDs — fill from env
DESTINATIONS = {
    "owner_pay": os.getenv("STRIPE_DEST_OWNER", ""),
    "operations": os.getenv("STRIPE_DEST_OPS", ""),
    "tax_reserve": os.getenv("STRIPE_DEST_TAX", ""),
    "reinvestment": os.getenv("STRIPE_DEST_REINVEST", ""),
}


class PayoutEvent(BaseModel):
    amount_cents: int
    currency: str = "usd"
    source_description: str = ""


def allocate(amount_cents: int) -> dict:
    """Return allocation breakdown in cents."""
    return {
        k: int(amount_cents * pct)
        for k, pct in ALLOCATION_RULES.items()
    }


def execute_allocation(amount_cents: int, currency: str = "usd") -> dict:
    """Execute Stripe transfers per allocation rules."""
    splits = allocate(amount_cents)
    results = {}
    for bucket, cents in splits.items():
        dest = DESTINATIONS.get(bucket)
        if dest:
            try:
                transfer = stripe.Transfer.create(
                    amount=cents,
                    currency=currency,
                    destination=dest,
                    description=f"Garcar auto-allocation: {bucket}",
                )
                results[bucket] = {"status": "transferred", "amount": cents, "transfer_id": transfer.id}
            except stripe.error.StripeError as e:
                results[bucket] = {"status": "error", "error": str(e), "amount": cents}
        else:
            results[bucket] = {"status": "no_destination_configured", "amount": cents}
    return results


# Standalone FastAPI app for allocation webhook
alloc_app = FastAPI(title="Revenue Allocator")


@alloc_app.post("/allocate")
async def allocate_endpoint(event: PayoutEvent):
    splits = allocate(event.amount_cents)
    return {
        "total_cents": event.amount_cents,
        "allocations": splits,
        "allocation_rules": ALLOCATION_RULES,
        "description": event.source_description,
    }


@alloc_app.post("/allocate/execute")
async def allocate_execute(event: PayoutEvent):
    """Actually execute transfers. Only call after Stripe payout confirmed."""
    results = execute_allocation(event.amount_cents, event.currency)
    return {"total_cents": event.amount_cents, "results": results}


@alloc_app.get("/health")
def health():
    return {"status": "ok", "service": "revenue-allocator"}
