"""Referral and advocacy stage. Proof, permission and live links are mandatory."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session


class ReferralStage:
    def __init__(self, db: Session):
        self.db = db

    def activate_advocacy(self, customer_id: str) -> Dict[str, Any]:
        """Do not advertise invented referral URLs, rewards or live programs."""
        return {
            "customer_id": customer_id,
            "stage": "referral",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "activated_at": None,
            "program": None,
            "referral_link": None,
            "money_events": [],
            "next_action": "configure_and_verify_referral_program",
            "status": "not_configured",
        }

    def generate_advocacy_assets(
        self, customer_id: str, outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Quarantine customer-submitted claims until permission and proof are checked.

        No case study is published or recycled as a new lead by this method.
        """
        return {
            "customer_id": customer_id,
            "case_study": None,
            "referrals": [],
            "roi": None,
            "generated_at": None,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_status": "requires_independent_verification_and_consent",
        }
