"""Trial stage: no activation or measured win without actual provisioning."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session


class TrialStage:
    def __init__(self, db: Session):
        self.db = db

    def activate_zero_friction_trial(self, prospect_id: str) -> Dict[str, Any]:
        """Do not report a live trial or scheduled win without provisioning receipts."""
        return {
            "prospect_id": prospect_id,
            "stage": "trial",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "activated_at": None,
            "trial_ends_at": None,
            "access_level": "none",
            "onboarding": {"mode": "manual_verification_required", "status": "not_started"},
            "forced_win": None,
            "money_events": [],
            "next_action": "provision_and_verify_real_customer_access",
            "status": "not_provisioned",
        }
