"""
Garcar Enterprise — Revenue Loop Entry Point
============================================
Does not move money by itself. A green run means the module imported.
Cash still requires a stranger paying the $47 storefront.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("revenue_loop")


def start_money_flow_loop(db: Optional[Session] = None) -> dict:
    if db is None:
        return {
            "status": "idle_no_db",
            "message": "No DB session. Organism did not process charges. Storefront remains https://garrettc123.github.io/",
            "paid_stranger_implied": False,
            "stages": [
                "attention",
                "trust",
                "trial",
                "conversion",
                "expansion",
                "referral",
            ],
        }

    from money_flow_loop.orchestrator import MoneyFlowOrchestrator

    orch = MoneyFlowOrchestrator(db)
    health = orch.health()
    logger.info("Money flow orchestrator health checked against a live DB session")
    return health


if __name__ == "__main__":
    result = start_money_flow_loop()
    print(result)
    print("Revenue loop process finished — not a payment confirmation.")
