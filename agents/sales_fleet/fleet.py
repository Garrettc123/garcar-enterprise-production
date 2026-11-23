"""Sales Fleet runtime — autonomous cycle that feeds the revenue loop."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from approval_gate import ApprovalRequired, require_approval  # GAR-530

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
    provider_id: Optional[str] = None
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
    sku = config.SKU_MAP[sku_key]
    first = (lead.contact_name or "there").split()[0]
    body = config.OUTREACH_TEMPLATE.format(
        first_name=first,
        vertical=lead.vertical,
        price=sku["price"],
        sku_url=sku["url"],
    )
    subject = f"{lead.company} — {sku['label']} (${sku['price']})"
    if sku_key == "2500":
        body = f"Hello {first},\n\nI can scope a callback timer and backup owner for your CRM. The one-time installation is ${sku['price']}. Which CRM would it need to support?\n\nGarrett Carrol"

    return OutreachPacket(
        lead=lead,
        subject=subject,
        body=body,
        sku_key=sku_key,
        sku_url=sku["url"] if sku_key == "497" else "",
        price=sku["price"],
    )


def send_email(packet: OutreachPacket, dry_run: bool | None = None) -> OutreachPacket:
    """Send via Resend when key present and not dry-run. Else leave as ready."""
    if (config.DRY_RUN if dry_run is None else dry_run):
        packet.sent = False
        packet.send_error = "dry_run"
        return packet
    if not packet.lead.eligible_for_outreach:
        packet.send_error = "verified_email_source_and_consent_required"
        return packet
    if not config.RESEND_API_KEY:
        packet.send_error = "resend_not_configured"
        return packet
    try:  # GAR-530: live sends need FLEET_APPROVAL_ID covering this recipient
        require_approval("send.email", config.APPROVAL_ID, to=packet.lead.email,
                         site="agents.sales_fleet.fleet.send_email")
    except ApprovalRequired as exc:
        packet.send_error = f"approval_required:{exc.reason}"
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
                receipt = json.load(resp)
                provider_id = receipt.get("id") if isinstance(receipt, dict) else None
                if isinstance(provider_id, str) and provider_id.strip():
                    packet.provider_id = provider_id
                    packet.sent = True
                else:
                    packet.send_error = "provider_acceptance_unknown"
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
            body = json.load(resp)
            ready = isinstance(body, dict) and body.get("ready_for_live_webhooks") is True and body.get("unsigned_local_test_enabled") is False
            return {"ok": ready, "status": resp.status, "url": url}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def append_ledger(result: FleetRunResult) -> None:
    path = Path(config.LEDGER_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if path.exists():
        history = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            raise ValueError("Existing ledger must contain a list")
    history.append(result.to_dict())
    path.write_text(json.dumps(history[-100:], indent=2), encoding="utf-8")


class SalesFleet:
    """Five-agent autonomous sales fleet."""

    def __init__(self, sku_key: str | None = None, limit: int | None = None):
        self.sku_key = sku_key or config.DEFAULT_SKU
        if self.sku_key not in config.SKU_MAP:
            raise ValueError("Unsupported sales fleet SKU")
        self.limit = config.MAX_LEADS_PER_RUN if limit is None else limit

    def run(self, dry_run: bool | None = None) -> FleetRunResult:
        dry_run = config.DRY_RUN if dry_run is None else dry_run
        started = datetime.now(timezone.utc)
        run_id = f"fleet_{started.strftime('%Y%m%dT%H%M%SZ')}"
        notes: List[str] = []

        leads = source_leads(limit=self.limit)
        notes.append(f"scout:sourced={len(leads)}")

        for lead in leads:
            lead.score = score_lead(lead)
        ranked = sorted(leads, key=lambda L: L.score, reverse=True)
        qualified = [L for L in ranked if L.score >= config.MIN_SCORE_TO_OUTREACH
                     and L.eligible_for_outreach]
        notes.append(f"scorer:qualified={len(qualified)} min={config.MIN_SCORE_TO_OUTREACH}")

        packets: List[OutreachPacket] = []
        sent = 0
        payments = check_payments_edge()
        for lead in qualified:
            packet = build_outreach(lead, sku_key=self.sku_key)
            if not dry_run and not payments.get("ok"):
                packet.send_error = "payments_health_unavailable"
            else:
                packet = send_email(packet, dry_run)
            if packet.sent:
                sent += 1
            packets.append(packet)

        if not payments.get("ok"):
            notes.append("watcher:payments_edge_degraded — fix before expecting cash")
        else:
            notes.append("watcher:payments_edge_ok")

        finished = datetime.now(timezone.utc)
        result = FleetRunResult(
            run_id=run_id,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            dry_run=dry_run,
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
                    "source": p.lead.source,
                    "source_id": p.lead.source_id,
                    "provider_id": p.provider_id,
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
    fleet = SalesFleet(sku_key=sku_key, limit=limit)
    return fleet.run(dry_run)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Garcar autonomous sales fleet")
    parser.add_argument("--sku", default=None, choices=list(config.SKU_MAP))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--live", action="store_true", help="Disable dry-run (sends email if Resend configured)"
    )
    args = parser.parse_args()
    result = run_fleet_once(sku_key=args.sku, limit=args.limit, dry_run=not args.live)
    summary = result.to_dict()
    summary.pop("packets")
    print(json.dumps(summary, indent=2))
    if not result.payments_health.get("ok") or (not result.dry_run and result.outreach_sent < result.outreach_ready):
        raise SystemExit(1)
