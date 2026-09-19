"""Sales Fleet configuration — live SKUs and ICP defaults."""
from __future__ import annotations

import os

# Live commercial surface (reconcile with operator if prices change this hour)
STOREFRONT = os.getenv("GARCAR_STOREFRONT", "https://garrettc123.github.io/")
SKU_47 = os.getenv(
    "GARCAR_SKU_47",
    "https://buy.stripe.com/dRm8wPbb72pY2Mz8BR43S1D",
)  # Contractor Lead Leak Audit
SKU_497 = os.getenv(
    "GARCAR_SKU_497",
    "https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h",
)  # Mark the leads that sat
SKU_2500 = os.getenv(
    "GARCAR_SKU_2500",
    "https://buy.stripe.com/6oUaEX4MJ0hQevhf0f43S2i",
)  # Lead backup — callback clock

# Payments control plane (webhook fixed 2026-09-19)
PAYMENTS_BASE = os.getenv(
    "GARCAR_PAYMENTS_URL",
    "https://garcar-payments.garrettc123.workers.dev",
)

DEFAULT_SKU = os.getenv("GARCAR_DEFAULT_SKU", "47")  # 47 | 497 | 2500
SKU_MAP = {
    "47": {"url": SKU_47, "label": "Contractor Lead Leak Audit", "price": 47},
    "497": {"url": SKU_497, "label": "Lead Export Review", "price": 497},
    "2500": {"url": SKU_2500, "label": "Lead Backup Callback Clock", "price": 2500},
}

# ICP: Texas trades (HVAC / roofing / plumbing / GC)
ICP_VERTICALS = [
    "HVAC",
    "roofing",
    "plumbing",
    "general contractor",
    "electrical",
]
ICP_TITLES = [
    "Owner",
    "President",
    "CEO",
    "Founder",
    "Principal",
    "VP Operations",
    "Director of Operations",
    "General Manager",
]
ICP_GEO = "DFW / North Texas / Grandview / Cleburne / Fort Worth / Dallas"

# Fleet limits (safe defaults)
MAX_LEADS_PER_RUN = int(os.getenv("FLEET_MAX_LEADS", "25"))
MIN_SCORE_TO_OUTREACH = float(os.getenv("FLEET_MIN_SCORE", "55"))
DRY_RUN = os.getenv("FLEET_DRY_RUN", "true").lower() in ("1", "true", "yes")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Garrett at Garcar <garrett@garcar.io>")
LEDGER_PATH = os.getenv("FLEET_LEDGER_PATH", "agents/sales_fleet/fleet_ledger.json")

# Outreach voice (from operator skill — Texas trades, not VC)
OUTREACH_TEMPLATE = """Hey {first_name} — I'm Garrett in Grandview. I write the 48-hour map of where Texas {vertical} shops lose jobs after the lead hits. First response gap is usually the money. ${price}, delivered to your email. If the map is wrong you say so.

{sku_url}

— Garrett
"""
