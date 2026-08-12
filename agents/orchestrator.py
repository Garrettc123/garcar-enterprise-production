"""
Garcar Enterprise — Agent Orchestrator
======================================
The deployment and coordination engine for the 341-agent lattice.

This is the permanent structural expansion of the original deployment signal.
Any agent can now be summoned by name, vertical, type, or complexity
and wired into the Money Flow Loop or any other Garcar subsystem.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .registry import AGENTS, get_agent, list_by_vertical, list_by_type, list_by_complexity

logger = logging.getLogger("garcar.agents")


class AgentOrchestrator:
    """
    Central controller for the full Agent Network.

    Responsibilities:
    - Register and inventory every agent
    - Deploy agents by name / vertical / type / complexity
    - Provide status and health of the lattice
    - Serve as the bridge between the Money Flow Loop and specialized agents
    """

    def __init__(self):
        self.deployed: Dict[str, Dict[str, Any]] = {}
        self.boot_time = datetime.now(timezone.utc)
        logger.info("AgentOrchestrator online — 341-agent lattice ready")

    def deploy(self, name: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deploy a single agent by name.
        Returns the agent record + deployment metadata.
        """
        agent = get_agent(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found in the lattice")

        deployment = {
            **agent,
            "status": "active",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "context": context or {},
        }
        self.deployed[name] = deployment

        logger.info(f"Deployed {name} [{agent.get('type') or 'untyped'} | {agent.get('vertical')}]")
        return deployment

    def deploy_vertical(self, vertical: str) -> List[Dict[str, Any]]:
        """Deploy every agent belonging to a vertical."""
        agents = list_by_vertical(vertical)
        results = []
        for a in agents:
            results.append(self.deploy(a["name"]))
        logger.info(f"Vertical '{vertical}' fully deployed — {len(results)} agents")
        return results

    def deploy_type(self, agent_type: str) -> List[Dict[str, Any]]:
        """Deploy every agent of a given type (Specialist, Autonomous, Orchestrator, etc.)."""
        agents = list_by_type(agent_type)
        results = []
        for a in agents:
            results.append(self.deploy(a["name"]))
        logger.info(f"Type '{agent_type}' fully deployed — {len(results)} agents")
        return results

    def deploy_all(self) -> Dict[str, Any]:
        """
        Full lattice activation.
        Every one of the 341 agents is brought online in a single call.
        """
        for agent in AGENTS:
            self.deploy(agent["name"])

        return {
            "status": "lattice_fully_online",
            "total_agents": len(AGENTS),
            "deployed_count": len(self.deployed),
            "boot_time": self.boot_time.isoformat(),
            "message": "All 341 agents are now permanent residents of Garcar Enterprise.",
        }

    def status(self) -> Dict[str, Any]:
        """Current health of the Agent Network."""
        by_type: Dict[str, int] = {}
        by_vertical: Dict[str, int] = {}

        for a in AGENTS:
            t = a.get("type") or "Untyped"
            v = a.get("vertical") or "Unknown"
            by_type[t] = by_type.get(t, 0) + 1
            by_vertical[v] = by_vertical.get(v, 0) + 1

        return {
            "total_agents": len(AGENTS),
            "currently_deployed": len(self.deployed),
            "boot_time": self.boot_time.isoformat(),
            "by_type": by_type,
            "by_vertical_sample": dict(list(by_vertical.items())[:12]),
            "status": "organism_expanded",
            "message": "The Agent Network is permanent infrastructure inside Garcar Enterprise.",
        }

    def summon_for_money_flow(self, stage: str) -> List[str]:
        """
        Recommend agents that are relevant to a Money Flow Loop stage.
        This is the bridge between the revenue organism and the specialist lattice.
        """
        mapping = {
            "attention": ["LeadNurtureBot", "AudienceAnalyzerMedia", "SocialListenBot", "TrendRadar"],
            "trust": ["BrandSentiment", "FactCheckerAI", "PRDraftBot", "ContentAccessibility"],
            "trial": ["PersonalizationBot", "OnboardPro", "IntegrationHelper"],
            "conversion": ["DealCloser", "PricingDynamo", "CheckoutOptimizer", "QuoteCraft"],
            "expansion": ["RetentionEngine", "LoyaltyProgramAI", "Upsell agents via RevenuePredictor"],
            "referral": ["CommunityManager", "InfluencerMatch", "ViralHookGen"],
        }
        return mapping.get(stage.lower(), [])
