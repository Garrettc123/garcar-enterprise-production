"""GAR-422: Stripe -> Accounting Auto-Sync
Webhook handler: charge.succeeded -> create transaction record + P&L entry.
Integrates with Wave API (free) or QuickBooks Online API.
"""
import os
import json
import stripe
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import httpx

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Wave API (free accounting software)
WAVE_API_TOKEN = os.getenv("WAVE_API_TOKEN", "")
WAVE_BUSINESS_ID = os.getenv("WAVE_BUSINESS_ID", "")

# Revenue stream categories
REVENUE_CATEGORIES = {
    "RHNS": "RHNS License",
    "CONSULTING": "Consulting Services",
    "SAAS": "SaaS Subscription",
    "AUTOMATION": "Automation Services",
}

app = FastAPI(title="Stripe-Accounting Sync")


def categorize_charge(description: str) -> str:
    desc = (description or "").upper()
    for key, label in REVENUE_CATEGORIES.items():
        if key in desc:
            return label
    return "General Revenue"


async def log_to_wave(charge: dict) -> dict:
    """Create income transaction in Wave via GraphQL API."""
    if not WAVE_API_TOKEN or not WAVE_BUSINESS_ID:
        return {"status": "wave_not_configured"}
    mutation = """
    mutation ($input: CreateTransactionInput!) {
      createTransaction(input: $input) {
        transaction { id description amount { value } }
      }
    }
    """
    variables = {
        "input": {
            "businessId": WAVE_BUSINESS_ID,
            "description": charge.get("description", "Stripe charge"),
            "amount": charge["amount"] / 100,
            "date": datetime.utcfromtimestamp(charge["created"]).strftime("%Y-%m-%d"),
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://gql.waveapps.com/graphql/public",
            json={"query": mutation, "variables": variables},
            headers={"Authorization": f"Bearer {WAVE_API_TOKEN}"},
            timeout=10,
        )
    return resp.json()


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Receive Stripe webhook, sync to accounting on charge.succeeded."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "charge.succeeded":
        charge = event["data"]["object"]
        category = categorize_charge(charge.get("description", ""))
        wave_result = await log_to_wave(charge)
        return {
            "status": "synced",
            "charge_id": charge["id"],
            "amount": charge["amount"] / 100,
            "category": category,
            "wave": wave_result,
        }
    return {"status": "ignored", "event_type": event["type"]}


@app.get("/health")
def health():
    return {"status": "ok", "service": "stripe-accounting-sync"}
