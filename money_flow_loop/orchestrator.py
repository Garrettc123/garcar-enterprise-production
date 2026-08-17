"""
Money Flow Loop Orchestrator
============================
The central nervous system of the real-money closed loop.
Tracks every prospect through every stage and forces progression
when value is delivered or money moves.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class LoopStage(str, Enum):
    ATTENTION = "attention"
    TRUST = "trust"
    TRIAL = "trial"
    CONVERSION = "conversion"
    EXPANSION = "expansion"
    REFERRAL = "referral"
    ADVOCATE = "advocate"


class MoneyFlowOrchestrator:
    """
    Fully autonomous revenue organism controller.

    Responsibilities:
    - Accept new attention events (leads, content engagement, demos)
    - Advance prospects through stages based on real signals
    - Trigger money events (checkout, upgrade, referral payouts)
    - Feed successful outcomes back into attention generation
    """

    def __init__(self, db: Session):
        self.db = db
        self.loop_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc)

    # ── Entry Points ──────────────────────────────────────────────────────

    def ingest_attention(
        self,
        source: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Stage 1 entry: cold or warm attention arrives.
        Creates a real Lead and immediately queues trust micro-proof.
        Returns the full prospect dict (including lead_id and email) so callers can act.
        """
        from .stages.attention import AttentionStage

        stage = AttentionStage(self.db)
        prospect = stage.capture(
            source=source,
            email=email,
            phone=phone,
            metadata=metadata or {},
            loop_id=self.loop_id,
        )

        logger.info(
            f"[LOOP {self.loop_id[:8]}] Attention captured → prospect {prospect.get('id')} lead_id={prospect.get('lead_id')} from {source}"
        )

        # Immediately advance toward trust
        advance_result = self.advance(prospect["id"], LoopStage.TRUST)

        # Merge so callers get both the prospect identity and the stage result
        return {
            **prospect,
            **advance_result,
            "prospect_id": prospect.get("id"),
            "lead_id": prospect.get("lead_id"),
            "email": prospect.get("email"),
            "db_persisted": prospect.get("db_persisted", False),
        }

    def advance(self, prospect_id: str, target_stage: LoopStage) -> Dict[str, Any]:
        """
        Force or evaluate progression to the next stage.
        Returns the updated prospect state + any money events fired.
        """
        handlers = {
            LoopStage.TRUST: self._run_trust,
            LoopStage.TRIAL: self._run_trial,
            LoopStage.CONVERSION: self._run_conversion,
            LoopStage.EXPANSION: self._run_expansion,
            LoopStage.REFERRAL: self._run_referral,
        }

        handler = handlers.get(target_stage)
        if not handler:
            raise ValueError(f"Unknown stage: {target_stage}")

        result = handler(prospect_id)
        result["loop_id"] = self.loop_id
        result["advanced_to"] = target_stage.value
        result["timestamp"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"[LOOP {self.loop_id[:8]}] Prospect {prospect_id} → {target_stage.value} | money_events={result.get('money_events', [])}"
        )
        return result

    # ── Stage Runners ─────────────────────────────────────────────────────

    def _run_trust(self, prospect_id: str) -> Dict[str, Any]:
        from .stages.trust import TrustStage

        stage = TrustStage(self.db)
        return stage.deliver_micro_proof(prospect_id)

    def _run_trial(self, prospect_id: str) -> Dict[str, Any]:
        from .stages.trial import TrialStage

        stage = TrialStage(self.db)
        return stage.activate_zero_friction_trial(prospect_id)

    def _run_conversion(self, prospect_id: str) -> Dict[str, Any]:
        from .stages.conversion import ConversionStage

        stage = ConversionStage(self.db)
        return stage.trigger_paid_conversion(prospect_id)

    def _run_expansion(self, prospect_id: str) -> Dict[str, Any]:
        from .stages.expansion import ExpansionStage

        stage = ExpansionStage(self.db)
        return stage.evaluate_and_upsell(prospect_id)

    def _run_referral(self, prospect_id: str) -> Dict[str, Any]:
        from .stages.referral import ReferralStage

        stage = ReferralStage(self.db)
        return stage.activate_advocacy(prospect_id)

    # ── Closed-Loop Feedback ──────────────────────────────────────────────

    def close_the_loop(self, customer_id: str, outcome: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called after a successful conversion or high-ROI period.
        Turns the customer into new attention fuel (case studies, referrals, content).
        """
        from .stages.referral import ReferralStage

        stage = ReferralStage(self.db)
        advocacy = stage.generate_advocacy_assets(customer_id, outcome)

        # Feed back into attention engine
        from .stages.attention import AttentionStage

        attention = AttentionStage(self.db)
        new_leads = attention.seed_from_advocacy(advocacy)

        return {
            "customer_id": customer_id,
            "advocacy_assets": advocacy,
            "new_attention_seeded": len(new_leads),
            "loop_status": "closed_and_amplified",
            "message": "Customer success has been converted into new acquisition fuel.",
        }

    def health(self) -> Dict[str, Any]:
        """Real-time loop health metrics for the dashboard."""
        return {
            "loop_id": self.loop_id,
            "started_at": self.started_at.isoformat(),
            "status": "organism_alive",
            "stages": [s.value for s in LoopStage],
            "message": "Real money flow loop is operational.",
        }
