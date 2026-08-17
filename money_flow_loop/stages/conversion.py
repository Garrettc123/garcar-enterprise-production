"""
Stage 4 — Paid Conversion
=========================
Turns trial users into paying customers via Stripe.
Integrates with existing backend/payments.py.

CRITICAL: Emits clear money_events and returns a payload the frontend
or agent can use to call /api/payments/create-checkout.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Mirror of the plans already defined in backend/payments.py
PLANS = {
    "starter": {"price_cents": 4900, "display": "$49/mo"},
    "professional": {"price_cents": 14900, "display": "$149/mo"},
    "enterprise": {"price_cents": 49900, "display": "$499/mo"},
}


class ConversionStage:
    def __init__(self, db: Session):
        self.db = db

    def trigger_paid_conversion(
        self,
        prospect_id: str,
        recommended_plan: str = "starter",
        user_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a conversion opportunity that the rest of the system can act on.
        Does NOT create a Stripe session itself (that requires an authenticated user).
        Instead it records the intent and returns the exact payload for create-checkout.
        """
        now = datetime.now(timezone.utc).isoformat()
        plan = PLANS.get(recommended_plan, PLANS["starter"])

        # Try to enrich from Lead if we have an id
        if lead_id and not email:
            try:
                from models import Lead
                lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
                if lead:
                    email = lead.email
                    # Mark as qualified when we push conversion
                    if lead.status in ("new", "contacted"):
                        lead.status = "qualified"
                        self.db.commit()
            except Exception as e:
                logger.warning(f"Could not enrich lead {lead_id}: {e}")

        checkout = {
            "plan": recommended_plan,
            "amount_cents": plan["price_cents"],
            "display_price": plan["display"],
            "checkout_endpoint": "/api/payments/create-checkout",
            "payload": {
                "plan": recommended_plan,
                "success_url": None,
                "cancel_url": None,
            },
            "requires_auth": True,
            "note": "Call create-checkout after user is authenticated or use guest checkout flow",
        }

        result = {
            "prospect_id": prospect_id,
            "lead_id": lead_id,
            "user_id": user_id,
            "email": email,
            "stage": "conversion",
            "triggered_at": now,
            "recommended_plan": recommended_plan,
            "checkout": checkout,
            "money_events": [
                {
                    "type": "checkout_opportunity_created",
                    "amount_cents": plan["price_cents"],
                    "currency": "usd",
                    "status": "pending",
                    "plan": recommended_plan,
                    "email": email,
                }
            ],
            "next_action": "complete_stripe_checkout",
            "status": "conversion_ready",
        }

        logger.info(
            f"Paid conversion triggered for prospect={prospect_id} lead={lead_id} email={email} → {recommended_plan} ({plan['display']})"
        )
        return result

    def record_successful_payment(
        self,
        prospect_id: str,
        plan: str,
        amount: float,
        stripe_subscription_id: str,
        user_id: Optional[int] = None,
        lead_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Called from the Stripe webhook after checkout.session.completed."""
        now = datetime.now(timezone.utc).isoformat()

        # Mark the Lead as converted if we can
        if lead_id:
            try:
                from models import Lead
                lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
                if lead:
                    lead.status = "converted"
                    lead.converted_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception as e:
                logger.warning(f"Could not mark lead {lead_id} converted: {e}")

        return {
            "prospect_id": prospect_id,
            "lead_id": lead_id,
            "user_id": user_id,
            "stage": "conversion",
            "converted_at": now,
            "plan": plan,
            "amount": amount,
            "stripe_subscription_id": stripe_subscription_id,
            "money_events": [
                {
                    "type": "subscription_started",
                    "amount": amount,
                    "currency": "usd",
                    "status": "succeeded",
                    "plan": plan,
                }
            ],
            "next_action": "begin_expansion_monitoring",
            "status": "paying_customer",
        }
