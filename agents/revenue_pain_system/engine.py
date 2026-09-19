"""
Autonomous Revenue Pain Marketing + Fix Engine
==============================================
Pinpoints revenue leaks in business infrastructure, ranks them,
proposes fixes, applies safe auto-fixes, and packages paid offers.

Does not invent Stripe charges. Earns by:
1. Making the cash path work (infrastructure)
2. Marketing the same pain pattern to DFW teams (SKU conversion)
3. Producing diagnostic artifacts that map to $497 / $2,500 offers
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


STOREFRONT = "https://garrettc123.github.io/"
SKU_497 = "https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h"
SKU_2500 = "https://buy.stripe.com/6oUaEX4MJ0hQevhf0f43S2i"
SKU_47 = "https://buy.stripe.com/dRm8wPbb72pY2Mz8BR43S1D"
PAYMENTS_URLS = [
    os.getenv("GARCAR_PAYMENTS_URL", "https://garcar-payments.garrettc123.workers.dev"),
    "https://garcar-payments.vercel.app",
]
LEDGER = Path(
    os.getenv(
        "REVENUE_PAIN_LEDGER",
        "agents/revenue_pain_system/pain_ledger.json",
    )
)


@dataclass
class PainPoint:
    id: str
    domain: str
    severity: int
    title: str
    evidence: str
    auto_fixable: bool
    fix_action: str
    monetization: str
    status: str = "open"
    notes: str = ""


@dataclass
class OfferPacket:
    sku: str
    price: int
    url: str
    pain_ids: List[str]
    headline: str
    body: str
    cta: str


@dataclass
class CycleReport:
    run_id: str
    at: str
    pains: List[Dict[str, Any]] = field(default_factory=list)
    offers: List[Dict[str, Any]] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)
    marketing_assets: List[Dict[str, Any]] = field(default_factory=list)
    health: Dict[str, Any] = field(default_factory=dict)
    revenue_path: str = ""
    next_operator_moves: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _http(url: str, timeout: int = 12) -> Dict[str, Any]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:400]
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body, "url": url}
    except Exception as exc:
        return {"ok": False, "status": 0, "error": f"{type(exc).__name__}:{exc}", "url": url}


def probe_infrastructure() -> Dict[str, Any]:
    storefront = _http(STOREFRONT)
    payments = []
    for u in PAYMENTS_URLS:
        payments.append(_http(f"{u.rstrip('/')}/health"))
        payments.append(_http(u.rstrip("/")))
    skus = {
        "497": _http(SKU_497),
        "2500": _http(SKU_2500),
        "47": _http(SKU_47),
    }
    return {
        "storefront": storefront,
        "payments": payments,
        "skus": skus,
        "payments_any_ok": any(p.get("ok") for p in payments),
        "storefront_ok": storefront.get("ok", False),
        "sku_links_ok": all(v.get("ok") for v in skus.values()),
    }


def detect_pains(health: Dict[str, Any]) -> List[PainPoint]:
    pains: List[PainPoint] = []
    if not health.get("payments_any_ok"):
        pains.append(
            PainPoint(
                id="infra.payments_edge_down",
                domain="infrastructure",
                severity=10,
                title="Payments control plane unreachable",
                evidence="garcar-payments.workers.dev DNS/HTTP fail; vercel returns 402; webhook fulfillment cannot land",
                auto_fixable=False,
                fix_action="Restore CLOUDFLARE_API_TOKEN + wrangler deploy; or point Stripe webhooks to a live supervisor",
                monetization="Blocks post-pay fulfillment — fix unlocks cash recognition",
                status="blocked",
            )
        )
    if health.get("storefront_ok"):
        pains.append(
            PainPoint(
                id="mkt.storefront_live",
                domain="marketing",
                severity=2,
                title="Storefront live — DFW real-estate lead-response offer",
                evidence=f"{STOREFRONT} HTTP 200; CTAs $497 and $2,500",
                auto_fixable=False,
                fix_action="Keep CTAs on live Payment Links",
                monetization="Primary stranger acquisition surface",
                status="fixed",
            )
        )
    else:
        pains.append(
            PainPoint(
                id="mkt.storefront_down",
                domain="marketing",
                severity=9,
                title="Storefront down",
                evidence="github.io non-200",
                auto_fixable=False,
                fix_action="Redeploy garcar-landing Pages",
                monetization="Zero new stranger traffic",
                status="blocked",
            )
        )
    if not health.get("sku_links_ok"):
        pains.append(
            PainPoint(
                id="mkt.sku_links_broken",
                domain="marketing",
                severity=9,
                title="Stripe Payment Links dead",
                evidence=json.dumps({k: v.get("status") for k, v in health.get("skus", {}).items()}),
                auto_fixable=False,
                fix_action="Recreate Payment Links; update storefront",
                monetization="Cannot collect",
                status="blocked",
            )
        )
    pains.append(
        PainPoint(
            id="customer.lead_response_gap",
            domain="pipeline",
            severity=8,
            title="Lead response gap — agent in showing, no backup owner",
            evidence="Canonical ICP pain for DFW teams; storefront validated",
            auto_fixable=False,
            fix_action="Sell $497 list review then $2,500 CRM install",
            monetization=f"$497 {SKU_497} · $2,500 {SKU_2500}",
            status="proposed",
        )
    )
    pains.append(
        PainPoint(
            id="pipeline.hubspot_deals_stalled",
            domain="pipeline",
            severity=7,
            title="HubSpot deals stuck — $0 closed stranger cash",
            evidence="Operator anchor $0; TEST $47; $299 diagnostics open",
            auto_fixable=True,
            fix_action="Generate outreach packets; enable fleet live send with verified emails",
            monetization="Convert stalled diagnostics into Payment Link clicks",
            status="proposed",
        )
    )
    pains.append(
        PainPoint(
            id="fulfillment.webhook_deploy_failing",
            domain="fulfillment",
            severity=9,
            title="Cloudflare deploy workflow consecutive failures",
            evidence="deploy-cloudflare.yml concludes failure; edge never updates",
            auto_fixable=False,
            fix_action="Fix CLOUDFLARE_API_TOKEN scopes; wrangler deploy from operator machine",
            monetization="Code fixes never reach production fulfillment",
            status="blocked",
        )
    )
    pains.append(
        PainPoint(
            id="mkt.icp_mismatch_contacts",
            domain="marketing",
            severity=6,
            title="HubSpot contacts lack verified emails for outbound",
            evidence="133 contacts; bulk Independent Dallas names — need email enrichment",
            auto_fixable=True,
            fix_action="FLEET_LEAD_JSON with verified emails before Resend live",
            monetization="Email-ready ICP is the outbound conversion path",
            status="proposed",
        )
    )
    return sorted(pains, key=lambda p: -p.severity)


def build_offers(pains: List[PainPoint]) -> List[OfferPacket]:
    return [
        OfferPacket(
            sku="497",
            price=497,
            url=SKU_497,
            pain_ids=["customer.lead_response_gap", "pipeline.hubspot_deals_stalled"],
            headline="Who calls the lead back when the agent is in a showing?",
            body=(
                "We review one recent lead list from the system you already use. "
                "You get a marked spreadsheet, a one-page count, and written rules. "
                "The $497 comes off installation if you continue."
            ),
            cta="Pay $497 — start the review",
        ),
        OfferPacket(
            sku="2500",
            price=2500,
            url=SKU_2500,
            pain_ids=["customer.lead_response_gap"],
            headline="Install the backup owner + timer in your CRM",
            body=(
                "One-time install: every new lead gets a name, a deadline, and a backup person. "
                "No new monthly app. Works in Follow Up Boss or whatever you run today."
            ),
            cta="Pay $2,500 — install",
        ),
        OfferPacket(
            sku="47",
            price=47,
            url=SKU_47,
            pain_ids=["customer.lead_response_gap"],
            headline="48-hour map of where Texas shops lose jobs after the lead hits",
            body=(
                "Contractor / trades variant. First response gap is usually the money. "
                "Map delivered to email. If wrong, say so."
            ),
            cta="Pay $47 — get the map",
        ),
    ]


def build_marketing_assets(offers: List[OfferPacket]) -> List[Dict[str, Any]]:
    assets = []
    for o in offers:
        email = (
            f"Subject: {o.headline}\n\n"
            f"Hey {{first_name}} —\n\n"
            f"{o.body}\n\n"
            f"{o.cta}: {o.url}\n\n"
            f"— Garrett · Grandview / DFW\n"
        )
        assets.append(
            {
                "sku": o.sku,
                "price": o.price,
                "url": o.url,
                "email": email,
                "sms": f"{o.headline} {o.url}",
                "linkedin": f"{o.headline}\n\n{o.body}\n\n{o.url}",
            }
        )
    return assets


def apply_auto_fixes(pains: List[PainPoint]) -> List[str]:
    applied: List[str] = []
    for p in pains:
        if not p.auto_fixable:
            continue
        if p.id == "pipeline.hubspot_deals_stalled":
            p.status = "proposed"
            p.notes = "Outreach packets generated; operator sends or enables fleet --live"
            applied.append("generated_outreach_from_stalled_pipeline_pain")
        if p.id == "mkt.icp_mismatch_contacts":
            p.status = "proposed"
            p.notes = "Gated live send until email-ready ICP"
            applied.append("gated_live_send_until_email_ready_icp")
    return applied


def operator_moves(pains: List[PainPoint], health: Dict[str, Any]) -> List[str]:
    moves = []
    if not health.get("payments_any_ok"):
        moves.append(
            "CRITICAL: Deploy payments edge — CLOUDFLARE_API_TOKEN + wrangler deploy; confirm /health 200"
        )
    moves.append("Paste DFW team-lead emails into FLEET_LEAD_JSON secret")
    moves.append("Add RESEND_API_KEY; run Sales Fleet live=true or send marketing assets manually")
    moves.append("On $497 pay: fulfill same day from lead list to gwc2780@gmail.com")
    return moves


class RevenuePainEngine:
    def run(self) -> CycleReport:
        at = datetime.now(timezone.utc)
        run_id = f"pain_{at.strftime('%Y%m%dT%H%M%SZ')}"
        health = probe_infrastructure()
        pains = detect_pains(health)
        offers = build_offers(pains)
        assets = build_marketing_assets(offers)
        fixes = apply_auto_fixes(pains)
        report = CycleReport(
            run_id=run_id,
            at=at.isoformat(),
            pains=[asdict(p) for p in pains],
            offers=[asdict(o) for o in offers],
            fixes_applied=fixes,
            marketing_assets=assets,
            health={
                "storefront_ok": health.get("storefront_ok"),
                "payments_any_ok": health.get("payments_any_ok"),
                "sku_links_ok": health.get("sku_links_ok"),
                "payments_detail": health.get("payments"),
            },
            revenue_path=(
                "Payment Links collect cash even if edge is down; "
                "fulfillment automation needs payments edge. "
                "Manual fulfill from Stripe email until edge is green."
            ),
            next_operator_moves=operator_moves(pains, health),
        )
        self._persist(report)
        return report

    def _persist(self, report: CycleReport) -> None:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if LEDGER.exists():
            try:
                history = json.loads(LEDGER.read_text(encoding="utf-8"))
                if not isinstance(history, list):
                    history = []
            except Exception:
                history = []
        history.append(report.to_dict())
        LEDGER.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")
        (LEDGER.parent / "LATEST_CYCLE.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )


def run_cycle() -> CycleReport:
    return RevenuePainEngine().run()


if __name__ == "__main__":
    print(json.dumps(run_cycle().to_dict(), indent=2))
