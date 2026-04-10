"""Stripe payments — checkout sessions, webhooks, subscription management."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
import logging

from database import get_db
from models import User, Payment
from auth import get_current_user
from rhns_audit import run_rhns_audit, STARTER_AUDIT_PRODUCT_IDS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Initialize Stripe
stripe = None
try:
    import stripe as stripe_lib
    if STRIPE_SECRET_KEY:
        stripe_lib.api_key = STRIPE_SECRET_KEY
        stripe = stripe_lib
        logger.info("Stripe initialized")
    else:
        logger.warning("STRIPE_SECRET_KEY not set — payments disabled")
except ImportError:
    logger.warning("stripe library not installed")

# Plan config
PLANS = {
    "starter": {
        "name": "Starter",
        "price": 4900,  # cents
        "display_price": "$49/mo",
        "features": [
            "AI Deal Desk — 100 analyses/month",
            "SEO Content Factory — 50 articles/month",
            "Churn Predictor — 200 predictions/month",
            "Email support",
            "API access (1,000 calls/month)",
        ],
    },
    "professional": {
        "name": "Professional",
        "price": 14900,
        "display_price": "$149/mo",
        "features": [
            "AI Deal Desk — 1,000 analyses/month",
            "SEO Content Factory — 500 articles/month",
            "Churn Predictor — 2,000 predictions/month",
            "Priority support",
            "API access (10,000 calls/month)",
            "Custom integrations",
            "Webhook notifications",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 49900,
        "display_price": "$499/mo",
        "features": [
            "All products — unlimited usage",
            "Dedicated support + Slack channel",
            "API access (unlimited)",
            "Custom model training",
            "White-label options",
            "SLA guarantee (99.9% uptime)",
            "Onboarding call",
        ],
    },
}


class CheckoutRequest(BaseModel):
    plan: str  # starter | professional | enterprise
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.get("/plans")
def list_plans():
    return {"plans": PLANS}


@router.post("/create-checkout")
def create_checkout(req: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe not configured. Set STRIPE_SECRET_KEY.")

    plan = PLANS.get(req.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose: {list(PLANS.keys())}")

    success_url = req.success_url or f"{BASE_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = req.cancel_url or f"{BASE_URL}/pricing"

    try:
        # Create or reuse Stripe customer
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email, name=user.name)
            user.stripe_customer_id = customer.id
            db.commit()

        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": plan["price"],
                        "recurring": {"interval": "month"},
                        "product_data": {"name": f"GARCAR {plan['name']}"},
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user.id), "plan": req.plan},
        )

        return {"checkout_url": session.url, "session_id": session.id}

    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment error: {str(e)}")


@router.get("/status")
def payment_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    last_payment = (
        db.query(Payment)
        .filter(Payment.user_id == user.id, Payment.status == "succeeded")
        .order_by(Payment.created_at.desc())
        .first()
    )
    return {
        "plan": user.plan,
        "stripe_customer_id": user.stripe_customer_id,
        "last_payment": {
            "amount": last_payment.amount if last_payment else 0,
            "date": str(last_payment.created_at) if last_payment else None,
            "plan": last_payment.plan if last_payment else None,
        },
    }


# --- Stripe Webhook ---
webhook_router = APIRouter(tags=["webhooks"])


@webhook_router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        else:
            import json
            event = json.loads(payload)
            logger.warning("Webhook signature not verified — STRIPE_WEBHOOK_SECRET not set")
    except Exception as e:
        logger.error(f"Webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    logger.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan = data.get("metadata", {}).get("plan", "starter")
        amount = data.get("amount_total", 0) / 100

        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.plan = plan
                user.stripe_customer_id = data.get("customer")
                payment = Payment(
                    user_id=user.id,
                    stripe_payment_id=data.get("payment_intent"),
                    stripe_subscription_id=data.get("subscription"),
                    amount=amount,
                    status="succeeded",
                    plan=plan,
                )
                db.add(payment)
                db.commit()
                logger.info(f"User {user.email} upgraded to {plan}")

        # Fire RHNS audit pipeline for Starter Audit purchases
        _handle_checkout_completed(data)

    elif event_type == "customer.subscription.updated":
        customer_id = data.get("customer")
        status = data.get("status")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user and status == "canceled":
            user.plan = "free"
            db.commit()
            logger.info(f"User {user.email} subscription canceled")

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.plan = "free"
            db.commit()
            logger.info(f"User {user.email} subscription deleted")

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            logger.warning(f"Payment failed for {user.email}")

    return {"status": "ok"}


# ── RHNS Audit Helpers ────────────────────────────────────────────────────────

def _handle_checkout_completed(session: dict):
    """
    Handles a completed Stripe checkout session.
    Detects Starter Audit purchases and fires the RHNS audit pipeline.
    """
    # Extract customer info
    customer_email = (
        session.get("customer_details", {}).get("email")
        or session.get("customer_email")
        or ""
    )
    customer_name = session.get("customer_details", {}).get("name") or ""
    metadata = session.get("metadata") or {}
    session_id = session.get("id", "")

    if not customer_email:
        logger.warning(f"Checkout session {session_id} has no customer email — skipping RHNS")
        return

    # Determine what was purchased
    line_items = _get_line_items(session_id)
    product_ids = {item.get("price", {}).get("product") for item in line_items}

    logger.info(f"Checkout complete — {customer_email} — products: {product_ids}")

    # ── Starter Audit purchase — fire RHNS audit pipeline ──
    if product_ids & STARTER_AUDIT_PRODUCT_IDS:
        logger.info(f"Starter Audit purchase detected — firing RHNS audit for {customer_email}")
        try:
            result = run_rhns_audit(
                customer_email=customer_email,
                customer_name=customer_name,
                company_name=metadata.get("company_name", ""),
                checkout_metadata=metadata,
                engagement_id=f"ENG-{session_id[:8].upper()}",
                upsell_url=os.getenv(
                    "RECOVERY_SPRINT_URL",
                    "https://buy.stripe.com/garcar-recovery-sprint",
                ),
            )
            logger.info(f"RHNS audit complete: {result}")
        except Exception as e:
            # Non-fatal — log and continue, don't fail the webhook response
            logger.error(f"RHNS audit failed for {customer_email}: {e}")

    # ── AI Growth Engine — trigger onboarding sequence ──
    ai_growth_engine_ids = set(
        os.getenv("AI_GROWTH_ENGINE_PRODUCT_IDS", "prod_AIGrowthEngine").split(",")
    )
    if product_ids & ai_growth_engine_ids:
        logger.info(f"AI Growth Engine purchase — triggering onboarding for {customer_email}")
        # TODO: fire onboarding sequence via nurture.py


def _get_line_items(session_id: str) -> list:
    """Retrieve line items for a checkout session from Stripe."""
    try:
        items = stripe.checkout.Session.list_line_items(session_id, limit=10)
        return items.get("data", [])
    except Exception as e:
        logger.warning(f"Could not fetch line items for session {session_id}: {e}")
        return []
