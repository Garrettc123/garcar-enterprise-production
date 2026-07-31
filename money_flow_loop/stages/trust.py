"""
Stage 2 — Trust Micro-Proof
===========================
Delivers instant, high-signal proof that the system works
before asking for any significant commitment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TrustStage:
    def __init__(self, db: Session):
        self.db = db

    def deliver_micro_proof(self, prospect_id: str) -> Dict[str, Any]:
        """
        Core trust actions:
        1. Show live activity counter / social proof wall
        2. Offer one-click "see it work on my number" demo
        3. Surface real (anonymized) results from similar businesses
        """
        now = datetime.now(timezone.utc).isoformat()

        # Simulated live metrics — in production these come from the real fleet
        live_proof = {
            "active_businesses_this_week": 47,
            "bookings_handled_last_24h": 312,
            "leads_recovered_last_7d": 89,
            "avg_roi_reported": "3.8x",
        }

        demo_offer = {
            "type": "one_click_ai_demo",
            "description": "See Zero-Human Reception handle a real call on a temporary number in under 60 seconds",
            "endpoint": f"/api/demo/activate/{prospect_id}",
            "ttl_seconds": 300,
        }

        similar_results = [
            {
                "vertical": "dental",
                "outcome": "+14 booked appointments in first 11 days",
                "anonymized": True,
            },
            {
                "vertical": "contractor",
                "outcome": "Recovered 9 dead leads → $18.4k pipeline",
                "anonymized": True,
            },
        ]

        result = {
            "prospect_id": prospect_id,
            "stage": "trust",
            "delivered_at": now,
            "live_proof": live_proof,
            "demo_offer": demo_offer,
            "similar_results": similar_results,
            "next_action": "activate_demo_or_start_trial",
            "money_events": [],  # no cash yet — pure trust capital
            "status": "micro_proof_delivered",
        }

        logger.info(f"Trust micro-proof delivered to prospect {prospect_id}")
        return result
