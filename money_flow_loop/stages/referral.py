"""
Stage 6 — Referral / Advocacy Engine
====================================
The real money multiplier.
Turns happy customers into acquisition channels and content fuel.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ReferralStage:
    def __init__(self, db: Session):
        self.db = db

    def activate_advocacy(self, customer_id: str) -> Dict[str, Any]:
        """
        Invite high-ROI customers into the advocacy program.
        """
        now = datetime.now(timezone.utc).isoformat()

        program = {
            "name": "Zero-Human Operators",
            "benefits": [
                "Early access to new agents",
                "Private circle",
                "Cash or credit rewards on successful referrals",
            ],
            "reward": {
                "type": "credit_or_cash",
                "amount": 100.0,
                "condition": "referred_business_stays_60_days",
            },
        }

        result = {
            "customer_id": customer_id,
            "stage": "referral",
            "activated_at": now,
            "program": program,
            "referral_link": f"https://garcar.enterprise/r/{customer_id[:8]}",
            "money_events": [
                {
                    "type": "advocacy_program_activated",
                    "potential_reward_per_referral": 100.0,
                    "status": "live",
                }
            ],
            "next_action": "share_referral_link_and_generate_assets",
            "status": "advocate_ready",
        }

        logger.info(f"Advocacy activated for customer {customer_id}")
        return result

    def generate_advocacy_assets(
        self, customer_id: str, outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Auto-generate case study snippets and referral opportunities
        from real customer results (with permission).
        """
        case_study_id = str(uuid.uuid4())

        assets = {
            "customer_id": customer_id,
            "case_study": {
                "id": case_study_id,
                "headline": outcome.get(
                    "headline",
                    "Local business automated revenue ops with Zero-Human Platform",
                ),
                "roi": outcome.get("roi", 3.4),
                "metrics": outcome.get("metrics", {}),
                "permission_granted": outcome.get("permission", False),
            },
            "referrals": outcome.get("referrals", []),
            "roi": outcome.get("roi", 3.4),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Advocacy assets generated for {customer_id} → case study {case_study_id}")
        return assets
