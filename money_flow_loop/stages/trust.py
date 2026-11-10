"""Evidence-gated trust stage.

Never synthesize customer counts, returns, testimonials, demos or case studies.
Proof is unavailable until linked, verifiable evidence is implemented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session


class TrustStage:
    def __init__(self, db: Session):
        self.db = db

    def deliver_micro_proof(self, prospect_id: str) -> Dict[str, Any]:
        """Fail closed: no proof is published without a verified source."""
        return {
            "prospect_id": prospect_id,
            "stage": "trust",
            "delivered_at": None,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "live_proof": None,
            "demo_offer": None,
            "similar_results": [],
            "next_action": "collect_and_verify_customer_evidence",
            "money_events": [],
            "status": "evidence_unavailable",
        }
