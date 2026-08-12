"""
Garcar Enterprise — Autonomous Agent Runtime
============================================
This is the process that never sleeps.

On every cycle it:
1. Deploys the highest-ROI revenue agents
2. Executes real actions through the RevenueEngine
3. Advances prospects through the Money Flow Loop
4. Surfaces conversion opportunities
5. Closes loops and feeds new attention

No human required. No more theory.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .orchestrator import AgentOrchestrator
from .revenue_engine import RevenueEngine

logger = logging.getLogger("garcar.runtime")

# Highest-ROI agents that are allowed to run autonomously
REVENUE_AGENTS = [
    "DealCloser",
    "PricingDynamo",
    "DynamicPricingAI",
    "LeadNurtureBot",
    "CheckoutOptimizer",
    "AdRevenueOptimizer",
    "RetentionEngine",
    "FraudDetectorEC",
    "PersonalizationBot",
    "RevenuePredictor",
    "CommunityManager",
    "InfluencerMatch",
]


class AutonomousRuntime:
    """
    The permanent background organism.
    Starts with the platform. Runs forever.
    """

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
        """Boot the lattice and begin the autonomous revenue cycle."""
        if self.running:
            logger.warning("Runtime already running")
            return

        # Deploy the money-makers first
        for name in REVENUE_AGENTS:
            try:
                self.orchestrator.deploy(name, context={"mode": "autonomous_revenue"})
            except Exception as e:
                logger.warning(f"Could not deploy {name}: {e}")

        self.running = True
        self.started_at = datetime.now(timezone.utc)
        self.task = asyncio.create_task(self._loop())
        logger.info("AUTONOMOUS REVENUE RUNTIME ONLINE — agents are now hunting")

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
        """The never-ending revenue cycle."""
        while self.running:
            try:
                await self._execute_cycle()
            except Exception as e:
                logger.error(f"Cycle error (continuing): {e}")
            await asyncio.sleep(self.cycle_seconds)

    async def _execute_cycle(self):
        """One full autonomous revenue pass."""
        self.total_cycles += 1
        self.engine.cycle_count = self.total_cycles
        self.last_cycle_at = datetime.now(timezone.utc)

        logger.info(f"=== REVENUE CYCLE {self.total_cycles} ===")

        # 1. Hunt new attention
        hunt = self.engine.hunt_and_capture(source=f"autonomous_cycle_{self.total_cycles}")
        logger.info(f"Hunt result: {hunt.get('status') or hunt.get('advanced_to') or 'ok'}")

        # 2. If we got a prospect, push it forward
        prospect_id = None
        if isinstance(hunt, dict):
            prospect_id = hunt.get("prospect_id") or hunt.get("id")
            # Some orchestrators return nested structures
            if not prospect_id and "prospect" in hunt:
                prospect_id = hunt["prospect"].get("id")

        if prospect_id:
            # Advance through the critical early stages
            for stage in ["trust", "trial"]:
                adv = self.engine.advance_pipeline(str(prospect_id), stage)
                logger.info(f"Advanced {prospect_id} → {stage}: {adv.get('advanced_to')}")

        # 3. Surface conversion opportunities (even without a specific prospect)
        #    This keeps the system aggressive
        self.engine.force_conversion_opportunity(
            email=f"cycle{self.total_cycles}@garcar.internal",
            plan="starter",
        )

        # 4. Churn / retention pass
        self.engine.run_churn_scan()

        logger.info(f"Cycle {self.total_cycles} complete — {len(self.engine.revenue_events)} total events")

    def status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "total_cycles": self.total_cycles,
            "cycle_seconds": self.cycle_seconds,
            "deployed_revenue_agents": list(self.orchestrator.deployed.keys()),
            "engine": self.engine.get_stats(),
            "message": "Agents are live and executing revenue actions." if self.running else "Runtime stopped",
        }


# Global singleton used by the API
_runtime: Optional[AutonomousRuntime] = None


def get_runtime(db_session_factory=None) -> AutonomousRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AutonomousRuntime(db_session_factory=db_session_factory)
    return _runtime
