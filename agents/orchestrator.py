"""GARCAR full-scale agent orchestrator.

The ExportBlock inventory is the capability source. This controller handles
identity, activation, filtering and dispatch. External side effects remain
adapter-gated and governed by the platform/CRF policies.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .fullscale import get_control_plane

logger = logging.getLogger("garcar.agents")


class AgentOrchestrator:
    def __init__(self):
        self.control = get_control_plane()
        self.deployed: Dict[str, Dict[str, Any]] = {}
        self.boot_time = datetime.now(timezone.utc)
        logger.info("AgentOrchestrator online — full ExportBlock inventory loaded")

    def _records(self) -> list[dict[str, Any]]:
        return self.control.agents

    def deploy(self, name: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        agent = self.control.get(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found in the full-scale inventory")
        self.control.activate([name])
        deployment = {
            **agent,
            "status": "active",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "context": context or {},
        }
        self.deployed[name] = deployment
        return deployment

    def deploy_all(self) -> Dict[str, Any]:
        result = self.control.activate()
        self.deployed = {
            a["name"]: {**a, "status": "active"} for a in self._records()
        }
        return {
            **result,
            "status": "lattice_fully_online",
            "deployed_count": len(self.deployed),
        }

    def deploy_vertical(self, vertical: str) -> List[Dict[str, Any]]:
        # ExportBlock names are authoritative; vertical metadata is retained in
        # the original registry. This method therefore supports exact names
        # and gracefully returns an empty result when no metadata match exists.
        try:
            from .registry import list_by_vertical
            names = [a["name"] for a in list_by_vertical(vertical)]
        except Exception:
            names = []
        return [self.deploy(n, {"vertical": vertical}) for n in names if self.control.get(n)]

    def deploy_type(self, agent_type: str) -> List[Dict[str, Any]]:
        try:
            from .registry import list_by_type
            names = [a["name"] for a in list_by_type(agent_type)]
        except Exception:
            names = []
        return [self.deploy(n, {"type": agent_type}) for n in names if self.control.get(n)]

    def dispatch(self, name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.control.dispatch(name, payload)

    def status(self) -> Dict[str, Any]:
        result = self.control.status()
        result.update({
            "currently_deployed": len(self.deployed),
            "boot_time": self.boot_time.isoformat(),
            "status": "organism_expanded",
        })
        return result

    def summon_for_money_flow(self, stage: str) -> List[str]:
        mapping = {
            "attention": ["LeadNurtureBot", "AudienceAnalyzerMedia", "SocialListenBot", "TrendRadar"],
            "trust": ["BrandSentiment", "FactCheckerAI", "PRDraftBot", "ContentAccessibility"],
            "trial": ["PersonalizationBot", "OnboardPro", "IntegrationHelper"],
            "conversion": ["DealCloser", "PricingDynamo", "CheckoutOptimizer", "QuoteCraft"],
            "expansion": ["RetentionEngine", "LoyaltyProgramAI", "RevenuePredictor"],
            "referral": ["CommunityManager", "InfluencerMatch", "ViralHookGen"],
        }
        return [n for n in mapping.get(stage.lower(), []) if self.control.get(n)]
