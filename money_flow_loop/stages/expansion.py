"""
Stage 5 — Expansion & Stickiness
================================
Usage-based and outcome-based upsells.
Automated health scoring + re-engagement when ROI dips.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ExpansionStage:
    def __init__(self, db: Session):
        self.db = db

    def evaluate_and_upsell(self, customer_id: str) -> Dict[str, Any]:
        """Do not score or upsell customers without verified billing and usage."""
        return {
            "customer_id": customer_id,
            "stage": "expansion",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "health": self._compute_health(customer_id),
            "upsell_candidates": [],
            "money_events": [],
            "next_action": "connect_real_billing_and_usage",
            "status": "evidence_unavailable",
        }

    def _compute_health(self, customer_id: str) -> Dict[str, Any]:
        """Unknown health is not zero: require source-backed metrics."""
        return {
            "customer_id": customer_id,
            "current_plan": None,
            "roi": None,
            "usage_percentile": None,
            "channels_active": None,
            "days_since_last_value": None,
            "churn_risk": None,
        }
