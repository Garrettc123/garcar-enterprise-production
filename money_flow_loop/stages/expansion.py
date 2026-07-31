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
        """
        Score customer health and surface the highest-probability expansion.
        """
        now = datetime.now(timezone.utc).isoformat()

        # In production these metrics come from real usage + revenue attribution
        health = self._compute_health(customer_id)

        upsell_candidates: List[Dict[str, Any]] = []

        if health["roi"] > 2.5 and health["usage_percentile"] > 0.7:
            upsell_candidates.append(
                {
                    "type": "plan_upgrade",
                    "from": health.get("current_plan", "starter"),
                    "to": "professional",
                    "reason": "High ROI + high usage — ready for next tier",
                    "estimated_mrr_lift": 100.0,
                }
            )

        if health["channels_active"] < 3:
            upsell_candidates.append(
                {
                    "type": "add_channel",
                    "product": "extra_ai_agent",
                    "reason": "Under-utilized channel capacity",
                    "estimated_mrr_lift": 49.0,
                }
            )

        if health["roi"] < 1.2:
            # Protective action instead of pure upsell
            upsell_candidates.append(
                {
                    "type": "success_intervention",
                    "action": "trigger_re_engagement_sequence",
                    "reason": "ROI below healthy threshold",
                    "estimated_mrr_lift": 0.0,
                }
            )

        result = {
            "customer_id": customer_id,
            "stage": "expansion",
            "evaluated_at": now,
            "health": health,
            "upsell_candidates": upsell_candidates,
            "money_events": [
                {
                    "type": "expansion_opportunity",
                    "potential_mrr_lift": sum(c.get("estimated_mrr_lift", 0) for c in upsell_candidates),
                    "status": "identified",
                }
            ],
            "next_action": "present_best_upsell_or_intervene",
            "status": "expansion_scored",
        }

        logger.info(
            f"Expansion evaluation for {customer_id}: ROI={health['roi']:.2f}, candidates={len(upsell_candidates)}"
        )
        return result

    def _compute_health(self, customer_id: str) -> Dict[str, Any]:
        """Placeholder — replace with real metrics from billing + usage tables."""
        return {
            "customer_id": customer_id,
            "current_plan": "starter",
            "roi": 3.4,
            "usage_percentile": 0.82,
            "channels_active": 2,
            "days_since_last_value": 3,
            "churn_risk": 0.12,
        }
