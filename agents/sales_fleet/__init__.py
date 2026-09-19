"""Autonomous Sales Fleet — Garcar Enterprise.

Five specialized agents that close the revenue loop end-to-end:

  Scout        → source / refresh ICP leads (DFW trades default)
  Scorer       → rank by fit (size, title, signal)
  Outreacher   → personalize + emit send-ready copy with live SKU link
  Closer       → attach checkout / payment link; optional Resend send
  Watcher      → confirm webhook path + ledger (fulfillment is payments side)

Revenue rule: strangers pay the live storefront or Payment Link.
This fleet only creates attention → trust → conversion opportunities.
It never fakes a charge.
"""

from .fleet import SalesFleet, FleetRunResult, run_fleet_once

__all__ = ["SalesFleet", "FleetRunResult", "run_fleet_once"]
