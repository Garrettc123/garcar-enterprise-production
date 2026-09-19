"""Sales Fleet runtime — autonomous cycle that feeds the revenue loop."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config
from .leads import Lead, source_leads


@dataclass
class OutreachPacket:
    lead: Lead
    subject: str
    body: str
    sku_key: str
    sku_url: str
    price: int
    sent: bool = False
    send_error: Optional[str] = None


@dataclass
class FleetRunResult:
    run_id: str
    started_at: str
    finished_at: str
    dry_run: bool
    leads_sourced: int
    leads_scored: int
    outreach_ready: int
    outreach_sent: int
    packets: List[Dict[str, Any]] = field(default_factory=list)
    payments_health: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def score_lead(lead: Lead) -> float:
    """Deterministic ICP score — no LLM required for the skeleton."""
    score = 40.0
    title = (lead.title or "").lower()
    for t in ("owner", "president", "ceo", "founder", "principal"):
        if t in title:
            score += 25
            break
    else:
        if "vp" in title or "director" in title or "gm" in title:
            score += 15
    if lead.email:
        score += 15
    if lead.vertical.lower() in [v.lower() for v in config.ICP_VERTICALS]:
        score += 10
    city = (lead.city or "").lower()
    if any(
        g in city
        for g in (
            "dallas",
            "fort worth",
            "arlington",
            "cleburne",
            "grandview",
            "dfw",
            "plano",
            "irving",
        )
    ):
        score += 10
    return min(100.0, score)


def build_outreach(lead: Lead, sku_key: str | None = None) -> OutreachPacket:
    sku_key = sku_key or config.DEFAULT_SKU
    sku = config.SKU_MAP.get(sku_key) or config.SKU_MAP["47"]
    first = (lead.contact_name or "there").split()[0]
    body = config.OUTREACH_TEMPLATE.format(
        first_name=first,
        vertical=lead.vertical,
        price=sku["price"],
        sku_url=sku["url"],
    )
    subject = f"{lead.company} — 48-hour lead leak map (${sku['price']})"
    return OutreachPacket(
        lead=lead,
        subject=subject,
        body=body,
        sku_key=sku_key,
        sku_url=sku["url"],
        price=sku["price"],
    )


def send_email(packet: OutreachPacket) -> OutreachPacket:
    """Send via Resend when key present and not dry-run. Else leave as ready."""
    if config.DRY_RUN:
        packet.sent = False
        packet.send_error = "dry_run"
        return packet
    if not packet.lead.email:
        packet.send_error = "no_email"
        return packet
    if not config.RESEND_API_KEY:
        packet.send_error = "resend_not_configured"
        return packet
    try:
        import urllib.request

        payload = json.dumps(
            {
                "from": config.EMAIL_FROM,
                "to": [packet.lead.email],
                "subject": packet.subject,
                "text": packet.body,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                packet.sent = True
            else:
                packet.send_error = f"resend_http_{resp.status}"
    except Exception as exc:
        packet.send_error = f"{type(exc).__name__}:{exc}"
    return packet


def check_payments_edge() -> Dict[str, Any]:
    """Confirm payments control plane (webhook path) is reachable."""
    import urllib.request

    url = f"{config.PAYMENTS_BASE.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body[:300]}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def append_ledger(result: FleetRunResult) -> None:
    path = Path(config.LEDGER_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history.append(result.to_dict())
    path.write_text(json.dumps(history[-100:], indent=2), encoding="utf-8")


class SalesFleet:
    """Five-agent autonomous sales fleet."""

    def __init__(self, sku_key: str | None = None, limit: int | None = None):
        self.sku_key = sku_key or config.DEFAULT_SKU
        self.limit = limit or config.MAX_LEADS_PER_RUN

    def run(self) -> FleetRunResult:
        started = datetime.now(timezone.utc)
        run_id = f"fleet_{started.strftime('%Y%m%dT%H%M%SZ')}"
        notes: List[str] = []

        leads = source_leads(limit=self.limit)
        notes.append(f"scout:sourced={len(leads)}")

        for lead in leads:
            lead.score = score_lead(lead)
        ranked = sorted(leads, key=lambda L: L.score, reverse=True)
        qualified = [L for L in ranked if L.score >= config.MIN_SCORE_TO_OUTREACH]
        notes.append(f"scorer:qualified={len(qualified)} min={config.MIN_SCORE_TO_OUTREACH}")

        packets: List[OutreachPacket] = []
        sent = 0
        for lead in qualified:
            packet = build_outreach(lead, sku_key=self.sku_key)
            packet = send_email(packet)
            if packet.sent:
                sent += 1
            packets.append(packet)

        payments = check_payments_edge()
        if not payments.get("ok"):
            notes.append("watcher:payments_edge_degraded — fix before expecting cash")
        else:
            notes.append("watcher:payments_edge_ok")

        finished = datetime.now(timezone.utc)
        result = FleetRunResult(
            run_id=run_id,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            dry_run=config.DRY_RUN,
            leads_sourced=len(leads),
            leads_scored=len(ranked),
            outreach_ready=len(packets),
            outreach_sent=sent,
            packets=[
                {
                    "company": p.lead.company,
                    "contact": p.lead.contact_name,
                    "email": p.lead.email,
                    "score": p.lead.score,
                    "vertical": p.lead.vertical,
                    "subject": p.subject,
                    "sku": p.sku_key,
                    "price": p.price,
                    "sku_url": p.sku_url,
                    "sent": p.sent,
                    "send_error": p.send_error,
                    "body_preview": p.body[:180],
                }
                for p in packets
            ],
            payments_health=payments,
            notes=notes,
        )
        append_ledger(result)
        return result


def run_fleet_once(
    sku_key: str | None = None,
    limit: int | None = None,
    dry_run: bool | None = None,
) -> FleetRunResult:
    if dry_run is not None:
        os.environ["FLEET_DRY_RUN"] = "true" if dry_run else "false"
        config.DRY_RUN = dry_run
    fleet = SalesFleet(sku_key=sku_key, limit=limit)
    return fleet.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Garcar autonomous sales fleet")
    parser.add_argument("--sku", default=None, choices=["47", "497", "2500"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--live", action="store_true", help="Disable dry-run (sends email if Resend configured)"
    )
    args = parser.parse_args()
    result = run_fleet_once(sku_key=args.sku, limit=args.limit, dry_run=not args.live)
    print(json.dumps(result.to_dict(), indent=2))
