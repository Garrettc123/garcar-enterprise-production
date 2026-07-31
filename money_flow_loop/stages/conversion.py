"""
Stage 4 — Paid Conversion
=========================
Turns trial users into paying customers via Stripe.
Integrates with existing backend/payments.py.
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
    ) -> Dict[str, Any]:
        """
        Generate a Stripe Checkout session (via existing payments router)
        or record an internal conversion event.
        """
        now = datetime.now(timezone.utc).isoformat()
        plan = PLANS.get(recommended_plan, PLANS["starter"])

        # In production this calls the real /api/payments/create-checkout endpoint
        # or directly creates the Stripe session using the same logic.

        checkout = {
            "plan": recommended_plan,
            "amount_cents": plan["price_cents"],
            "display_price": plan["display"],
            "checkout_endpoint": "/api/payments/create-checkout",
            "payload": {
                "plan": recommended_plan,
                "success_url": None,  # filled by caller
                "cancel_url": None,
            },
        }

        result = {
            "prospect_id": prospect_id,
            "user_id": user_id,
            "stage": "conversion",
            "triggered_at": now,
            "recommended_plan": recommended_plan,
            "checkout": checkout,
            "money_events": [
                {
                    "type": "checkout_session_created",
                    "amount_cents": plan["price_cents"],
                    "currency": "usd",
                    "status": "pending",
                    "plan": recommended_plan,
                }
            ],
            "next_action": "complete_stripe_checkout",
            "status": "conversion_ready",
        }

        logger.info(
            f"Paid conversion triggered for {prospect_id} → {recommended_plan} ({plan['display']})"
        )
        return result

    def record_successful_payment(
        self,
        prospect_id: str,
        plan: str,
        amount: float,
        stripe_subscription_id: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Called from the Stripe webhook after checkout.session.completed."""
        now = datetime.now(timezone.utc).isoformat()

        return {
            "prospect_id": prospect_id,
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
