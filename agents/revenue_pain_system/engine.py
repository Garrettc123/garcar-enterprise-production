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


STOREFRONT = "https://garcar-customer-acquisition-production.up.railway.app/"
SKU_497 = "https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h"
SKU_2500 = "https://garcar-followup-review.vercel.app/products/lead-backup-installation/"
PAYMENTS_URLS = [
    os.getenv("GARCAR_PAYMENTS_URL", "https://garcar-emergency-payments-production.up.railway.app"),
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
        result = _http(f"{u.rstrip('/')}/health")
        try:
            payload = json.loads(result.get("body", ""))
        except ValueError:
            payload = {}
        result["ok"] = bool(result["ok"] and isinstance(payload, dict) and payload.get("ready_for_live_webhooks") is True and payload.get("unsigned_local_test_enabled") is False)
        payments.append(result)

    skus = {
        "497": _http(SKU_497),
        "2500": _http(SKU_2500),
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
                evidence=json.dumps([{k: p.get(k) for k in ("url", "status", "ok")} for p in health.get("payments", [])]),
                auto_fixable=False,
                fix_action="Inspect the configured receiver health and provider deployment logs",
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
                title="Acquisition page reachable",
                evidence=f"{STOREFRONT} HTTP {health['storefront']['status']}",
                auto_fixable=False,
                fix_action="Keep CTAs on live Payment Links",
                monetization="Primary stranger acquisition surface",
                status="observed",
            )
        )
    else:
        pains.append(
            PainPoint(
                id="mkt.storefront_down",
                domain="marketing",
                severity=9,
                title="Storefront down",
                evidence=f"{STOREFRONT} HTTP {health['storefront']['status']}",
                auto_fixable=False,
                fix_action="Check the acquisition service and domain",
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
                title="Configured offer page unavailable",
                evidence=json.dumps({k: v.get("status") for k, v in health.get("skus", {}).items()}),
                auto_fixable=False,
                fix_action="Verify the offer in its source system",
                monetization="Cannot collect",
                status="blocked",
            )
        )
    return sorted(pains, key=lambda p: -p.severity)


def build_offers(pains: List[PainPoint]) -> List[OfferPacket]:
    return [
        OfferPacket(
            sku="497",
            price=497,
            url=SKU_497,
            pain_ids=[],
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
            pain_ids=[],
            headline="Install the backup owner + timer in your CRM",
            body=(
                "One-time install: every new lead gets a name, a deadline, and a backup person. "
                "No new monthly app. Confirm CRM compatibility and scope before payment."
            ),
            cta="Review installation scope",
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


def operator_moves(pains: List[PainPoint], health: Dict[str, Any]) -> List[str]:
    return [pain.fix_action for pain in pains if pain.status == "blocked"]


class RevenuePainEngine:
    def run(self) -> CycleReport:
        at = datetime.now(timezone.utc)
        run_id = f"pain_{at.strftime('%Y%m%dT%H%M%SZ')}"
        health = probe_infrastructure()
        pains = detect_pains(health)
        offers = build_offers(pains)
        assets = build_marketing_assets(offers)
        report = CycleReport(
            run_id=run_id,
            at=at.isoformat(),
            pains=[asdict(p) for p in pains],
            offers=[asdict(o) for o in offers],
            fixes_applied=[],
            marketing_assets=assets,
            health={
                "storefront_ok": health.get("storefront_ok"),
                "payments_any_ok": health.get("payments_any_ok"),
                "sku_links_ok": health.get("sku_links_ok"),
                "payments_detail": health.get("payments"),
            },
            revenue_path="HTTP probes measure reachability. Confirm payments and delivery using provider receipts.",
            next_operator_moves=operator_moves(pains, health),
        )
        self._persist(report)
        return report

    def _persist(self, report: CycleReport) -> None:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if LEDGER.exists():
            history = json.loads(LEDGER.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                raise ValueError("Existing ledger must contain a list")
        history.append(report.to_dict())
        LEDGER.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")
        (LEDGER.parent / "LATEST_CYCLE.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )


def run_cycle() -> CycleReport:
    return RevenuePainEngine().run()


if __name__ == "__main__":
    report = run_cycle()
    print(json.dumps(report.to_dict(), indent=2))
    if any(p["status"] == "blocked" for p in report.pains):
        raise SystemExit(1)
