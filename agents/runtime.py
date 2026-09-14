"""GARCAR autonomous runtime.

The runtime boots the complete registered capability lattice while keeping
external side effects adapter-gated. Revenue automation remains the first
production workload; the rest of the inventory is addressable on demand.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .orchestrator import AgentOrchestrator
from .revenue_engine import RevenueEngine

logger = logging.getLogger("garcar.runtime")

REVENUE_AGENTS = [
    "DealCloser", "PricingDynamo", "DynamicPricingAI", "LeadNurtureBot",
    "CheckoutOptimizer", "AdRevenueOptimizer", "RetentionEngine",
    "FraudDetectorEC", "PersonalizationBot", "RevenuePredictor",
    "CommunityManager", "InfluencerMatch",
]


class AutonomousRuntime:
    def __init__(self, db_session_factory=None, cycle_seconds: int = 90):
        self.orchestrator = AgentOrchestrator()
        self.engine = RevenueEngine(db_session_factory=db_session_factory)
        self.cycle_seconds = cycle_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.started_at: Optional[datetime] = None
        self.last_cycle_at: Optional[datetime] = None
        self.total_cycles = 0

    async def start(self):
        if self.running:
            return
        # Full-scale means all registered identities are online/addressable.
        # It does NOT mean every agent receives external side-effect access.
        result = self.orchestrator.deploy_all()
        logger.info("FULL-SCALE AGENT LATTICE ONLINE: %s agents", result.get("deployed_count"))
        self.started_at = datetime.now(timezone.utc)
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Autonomous runtime stopped")

    async def _loop(self):
        while self.running:
            try:
                await self._execute_cycle()
            except Exception as e:
                logger.error("Cycle error (continuing): %s", e)
            await asyncio.sleep(self.cycle_seconds)

    async def _execute_cycle(self):
        self.total_cycles += 1
        self.engine.cycle_count = self.total_cycles
        self.last_cycle_at = datetime.now(timezone.utc)
        logger.info("=== REVENUE CYCLE %s ===", self.total_cycles)

        hunt = self.engine.hunt_and_capture(source=f"autonomous_cycle_{self.total_cycles}")
        prospect_id = None
        email = None
        if isinstance(hunt, dict):
            prospect_id = hunt.get("prospect_id") or hunt.get("id")
            email = hunt.get("email")
            if not prospect_id and "prospect" in hunt:
                p = hunt["prospect"]
                prospect_id = p.get("id")
                email = p.get("email") or email

        if prospect_id:
            for stage in ["trust", "trial"]:
                self.engine.advance_pipeline(str(prospect_id), stage)
            if email and not email.endswith("@garcar.internal"):
                self.engine.force_conversion_opportunity(email=email, plan="starter")

        self.engine.run_churn_scan()

    def status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "total_cycles": self.total_cycles,
            "cycle_seconds": self.cycle_seconds,
            "agent_lattice": self.orchestrator.status(),
            "revenue_agents": [n for n in REVENUE_AGENTS if self.orchestrator.control.get(n)],
            "engine": self.engine.get_stats(),
            "message": "Full agent capability lattice is online; revenue execution is governed separately.",
        }


_runtime: Optional[AutonomousRuntime] = None


def get_runtime(db_session_factory=None) -> AutonomousRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AutonomousRuntime(db_session_factory=db_session_factory)
    return _runtime
