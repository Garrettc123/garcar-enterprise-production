"""
Garcar Enterprise — Revenue Loop Entry Point
============================================
Replaces the previous stub.
Now boots the full real-money flow loop organism.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("revenue_loop")


def start_money_flow_loop(db: Optional[Session] = None) -> dict:
    """
    Boot the closed-loop revenue organism.
    Call this from backend startup or a worker.
    """
    from money_flow_loop.orchestrator import MoneyFlowOrchestrator

    if db is None:
        # Allow standalone health check without DB
        return {
            "status": "organism_ready",
            "message": "Real money flow loop is loaded. Pass a DB session for full operation.",
            "stages": [
                "attention",
                "trust",
                "trial",
                "conversion",
                "expansion",
                "referral",
            ],
        }

    orch = MoneyFlowOrchestrator(db)
    health = orch.health()
    logger.info("Real money flow loop organism is ALIVE")
    return health


if __name__ == "__main__":
    result = start_money_flow_loop()
    print(result)
    print("Revenue loop active — ready for real money movement.")
