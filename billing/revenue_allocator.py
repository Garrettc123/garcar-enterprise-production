"""GAR-421: Revenue Allocation Rules
40% Owner Pay / 25% Ops / 20% Tax Reserve / 15% Reinvest
Trigger: Stripe payout webhook or manual call.
"""
import os
import stripe
from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

try:  # GAR-530 approval gate (repo-root package)
    from approval_gate import ApprovalRequired, require_approval
except ImportError:  # started from inside billing/: make the repo root importable
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from approval_gate import ApprovalRequired, require_approval
try:
    from billing.api_key_auth import api_key_dependency
except ImportError:  # started from inside billing/
    from api_key_auth import api_key_dependency

# Hardening audit Oct 2026: /allocate/execute moves money, so it needs ALLOCATOR_API_KEY
# on top of the GAR-530 approval. Fails closed (503) when ALLOCATOR_API_KEY is not set.
require_allocator_key = api_key_dependency("ALLOCATOR_API_KEY")

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
    approval_id: Optional[str] = None  # GAR-530: Garrett-issued money.transfer approval


def allocate(amount_cents: int) -> dict:
    """Return allocation breakdown in cents."""
    return {
        k: int(amount_cents * pct)
        for k, pct in ALLOCATION_RULES.items()
    }


def execute_allocation(amount_cents: int, currency: str = "usd",
                       approval_id: Optional[str] = None) -> dict:
    """Execute Stripe transfers per allocation rules.

    GAR-530: the whole allocation needs one Garrett-issued ``money.transfer`` approval
    whose cap covers ``amount_cents``. Raises ApprovalRequired otherwise.
    """
    require_approval("money.transfer", approval_id, amount_cents=amount_cents, currency=currency,
                     site="billing.revenue_allocator.execute_allocation")
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


@alloc_app.post("/allocate/execute", dependencies=[Depends(require_allocator_key)])
async def allocate_execute(event: PayoutEvent):
    """Actually execute transfers. Only call after Stripe payout confirmed."""
    try:
        results = execute_allocation(event.amount_cents, event.currency, approval_id=event.approval_id)
    except ApprovalRequired as exc:
        raise HTTPException(status_code=403, detail=f"approval_required:{exc.reason}")
    return {"total_cents": event.amount_cents, "results": results}


@alloc_app.get("/health")
def health():
    return {"status": "ok", "service": "revenue-allocator"}
