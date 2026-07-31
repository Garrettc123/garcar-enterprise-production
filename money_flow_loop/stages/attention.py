"""
Stage 1 — Attention Capture
===========================
Turns cold/warm traffic into tracked prospects.
Sources: LinkedIn, content factory, outreach sequences, SEO, referrals.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AttentionStage:
    def __init__(self, db: Session):
        self.db = db

    def capture(
        self,
        source: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        loop_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a new attention event and create a prospect.
        In production this writes to the leads / prospects table.
        """
        prospect_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        prospect = {
            "id": prospect_id,
            "email": email,
            "phone": phone,
            "source": source,
            "stage": "attention",
            "loop_id": loop_id,
            "metadata": metadata or {},
            "captured_at": now,
            "score": self._score_source(source),
            "status": "active",
        }

        # TODO: persist to DB via models.Lead or equivalent
        # For now we return the in-memory structure so the orchestrator can advance.
        logger.info(f"Attention captured: {prospect_id} via {source} (score={prospect['score']})")

        return prospect

    def seed_from_advocacy(self, advocacy_assets: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Closed-loop feedback: turn customer success into new attention.
        Creates content seeds and referral leads from advocacy assets.
        """
        seeds = []

        if advocacy_assets.get("case_study"):
            seeds.append(
                self.capture(
                    source="advocacy_case_study",
                    metadata={
                        "case_study_id": advocacy_assets["case_study"].get("id"),
                        "customer_roi": advocacy_assets.get("roi"),
                    },
                )
            )

        for referral in advocacy_assets.get("referrals", []):
            seeds.append(
                self.capture(
                    source="customer_referral",
                    email=referral.get("email"),
                    phone=referral.get("phone"),
                    metadata={
                        "referrer_id": advocacy_assets.get("customer_id"),
                        "incentive": referral.get("incentive"),
                    },
                )
            )

        logger.info(f"Seeded {len(seeds)} new attention events from advocacy")
        return seeds

    def _score_source(self, source: str) -> float:
        """Simple source quality scoring. Higher = warmer."""
        scores = {
            "customer_referral": 0.95,
            "advocacy_case_study": 0.85,
            "linkedin_founder": 0.75,
            "demo_request": 0.90,
            "seo_content": 0.55,
            "cold_outreach": 0.40,
            "paid_ad": 0.45,
        }
        return scores.get(source, 0.50)
