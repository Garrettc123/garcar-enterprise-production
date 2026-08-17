"""
Stage 1 — Attention Capture
===========================
Turns cold/warm traffic into tracked prospects.
Sources: LinkedIn, content factory, outreach sequences, SEO, referrals.

CRITICAL FIX: Now persists to the real Lead model so the rest of the
system (nurture, conversion, agents) can see and act on the prospect.
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
        Record a new attention event and create a real Lead in the database.
        Returns a prospect dict that includes both the UUID and the DB lead id.
        """
        from models import Lead  # local import to avoid circulars at module load

        prospect_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        meta = metadata or {}

        # Prefer real email; fall back to a trackable synthetic only if needed
        lead_email = email or meta.get("email")
        if not lead_email:
            # Still create a record so the loop can progress; mark clearly
            lead_email = f"prospect-{prospect_uuid[:8]}@garcar.internal"

        lead_name = meta.get("name") or meta.get("full_name") or None

        # Upsert by email — never create duplicates
        existing = self.db.query(Lead).filter(Lead.email == lead_email).first()
        if existing:
            # Refresh source/notes if we have better signal
            if source and existing.source != source:
                existing.notes = (existing.notes or "") + f"\n[loop] re-touched via {source} at {now.isoformat()}"
                self.db.commit()
            prospect = {
                "id": prospect_uuid,
                "lead_id": existing.id,
                "email": existing.email,
                "name": existing.name,
                "source": existing.source,
                "stage": "attention",
                "loop_id": loop_id,
                "metadata": meta,
                "captured_at": now.isoformat(),
                "score": self._score_source(source),
                "status": existing.status,
                "db_persisted": True,
            }
            logger.info(f"Attention re-touched existing lead {existing.id} ({lead_email}) via {source}")
            return prospect

        # New Lead
        lead = Lead(
            email=lead_email,
            name=lead_name,
            source=source or "money_flow_loop",
            status="new",
            notes=f"loop_id={loop_id} | prospect_uuid={prospect_uuid} | meta={meta}",
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        prospect = {
            "id": prospect_uuid,
            "lead_id": lead.id,
            "email": lead.email,
            "name": lead.name,
            "source": lead.source,
            "stage": "attention",
            "loop_id": loop_id,
            "metadata": meta,
            "captured_at": now.isoformat(),
            "score": self._score_source(source),
            "status": "new",
            "db_persisted": True,
        }

        logger.info(
            f"Attention captured & PERSISTED: lead_id={lead.id} uuid={prospect_uuid} via {source} (score={prospect['score']})"
        )
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
            "agent_autonomous": 0.35,
            "money_flow_loop": 0.30,
        }
        return scores.get(source, 0.50)
