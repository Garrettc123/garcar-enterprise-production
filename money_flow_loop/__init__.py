"""
Garcar Enterprise — Real Money Flow Loop
========================================
Closed-loop revenue organism:
Attention → Trust Micro-Proof → Zero-Friction Trial → Instant Value →
Paid Conversion → Expansion → Referral/Advocacy → New Attention

Every stage produces measurable cash or high-probability cash events.
"""

from .orchestrator import MoneyFlowOrchestrator
from .stages import (
    AttentionStage,
    TrustStage,
    TrialStage,
    ConversionStage,
    ExpansionStage,
    ReferralStage,
)

__all__ = [
    "MoneyFlowOrchestrator",
    "AttentionStage",
    "TrustStage",
    "TrialStage",
    "ConversionStage",
    "ExpansionStage",
    "ReferralStage",
]
