"""
Stage 3 — Zero-Friction Trial + Instant Value
=============================================
14-day (or $1) full-feature trial.
System forces at least one measurable win in the first 48 hours.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TrialStage:
    def __init__(self, db: Session):
        self.db = db

    def activate_zero_friction_trial(self, prospect_id: str) -> Dict[str, Any]:
        """
        - Provision full production access
        - Auto-onboard (Google listing, calendar, phone)
        - Schedule forced first-win within 48h
        """
        now = datetime.now(timezone.utc)
        trial_ends = now + timedelta(days=14)

        # In production: call the real provisioning pipeline
        # (see .github/workflows/provision-customer.yml and backend)

        forced_win = {
            "target": "first_measurable_value",
            "deadline": (now + timedelta(hours=48)).isoformat(),
            "possible_wins": [
                "booked_appointment",
                "recovered_lead",
                "follow_up_sequence_reactivated",
            ],
            "status": "scheduled",
        }

        result = {
            "prospect_id": prospect_id,
            "stage": "trial",
            "activated_at": now.isoformat(),
            "trial_ends_at": trial_ends.isoformat(),
            "access_level": "full_production",
            "onboarding": {
                "mode": "autonomous",
                "required": ["google_listing", "calendar", "phone_number"],
                "status": "ready_to_collect",
            },
            "forced_win": forced_win,
            "money_events": [
                {
                    "type": "trial_activation",
                    "amount": 0.0,  # or 1.00 if $1 activation
                    "currency": "usd",
                    "note": "Zero-friction entry — value first",
                }
            ],
            "next_action": "deliver_forced_win_then_convert",
            "status": "trial_live",
        }

        logger.info(f"Zero-friction trial activated for {prospect_id} — forced win in 48h")
        return result
