"""Deterministic fallback so ATLAS ships cash copy without an LLM key."""

from __future__ import annotations

from .config import settings
from .schemas import AuditPacket, LeakReport, NamedLeak, ShopIntake


def analyze(intake: ShopIntake) -> LeakReport:
    missed = int(intake.jobs_week * 0.25 * intake.close_rate * intake.ticket * 4)
    slow = int(intake.jobs_week * 0.15 * intake.close_rate * intake.ticket * 4)
    estimate = int(intake.jobs_week * 0.10 * intake.close_rate * intake.ticket * 4)
    after_hours = int(intake.jobs_week * 0.08 * intake.close_rate * intake.ticket * 4)
    no_follow = int(intake.jobs_week * 0.12 * intake.close_rate * intake.ticket * 4)
    leaks = [
        NamedLeak(
            name="First-response gap",
            where="Lead hits Google/FB/form; first human reply > 15 minutes",
            monthly_cost=missed,
            fix="Route every new lead to one named owner with a 5-minute SLA",
        ),
        NamedLeak(
            name="Missed-call black hole",
            where="Shop line rings out after hours and weekends",
            monthly_cost=after_hours,
            fix="Missed-call SMS in under 60 seconds with a booking link",
        ),
        NamedLeak(
            name="Estimate sits unsigned",
            where="Visit done, quote emailed, no follow-up clock",
            monthly_cost=estimate,
            fix="Day-1 / Day-3 / Day-7 text sequence on silent estimates",
        ),
        NamedLeak(
            name="Shared lead race",
            where="Angi/Thumbtack lead also sold to 3 other shops",
            monthly_cost=slow,
            fix="Call inside 3 minutes or drop the source",
        ),
        NamedLeak(
            name="No next appointment on old names",
            where="Past customers sit with no seasonal touch",
            monthly_cost=no_follow,
            fix="One weekly list of open tickets with a named caller",
        ),
    ]
    return LeakReport(
        shop=intake.shop,
        first_response_minutes=90,
        leaks=leaks,
        monthly_leak_total=sum(x.monthly_cost for x in leaks),
        first_workflow="Missed-call SMS in under 60 seconds with a booking link.",
    )


def write_map(intake: ShopIntake, report: LeakReport) -> AuditPacket:
    leak_lines = []
    for i, leak in enumerate(report.leaks, 1):
        leak_lines.append(
            f"{i}. **{leak.name}** — {leak.where}\n"
            f"   Monthly $: {leak.monthly_cost:,}\n"
            f"   One fix: {leak.fix}"
        )
    md = f"""# Contractor Lead Leak Audit

- Client: {intake.shop}
- Trade / city: {intake.trade} / {intake.city}
- Owner: {intake.owner or "unknown"}
- Paid date: (fill on Stripe clear)
- Stripe id: (fill on Stripe clear)
- Delivery deadline: paid + 48h

## 1. How work is supposed to arrive
Sources you actually use: {intake.sources}

## 2. First-response clock
- Who sees the lead first: unassigned / first person who picks up
- Minutes until first human reply: ~{report.first_response_minutes} (replace with their number)
- After-hours path: voicemail
- Weekend path: voicemail
- Leak $ estimate: ${report.monthly_leak_total:,}/mo modeled from {intake.jobs_week} jobs/wk × {intake.close_rate:.0%} close × ${intake.ticket:,} ticket

## 3. Estimate path
- Who writes it: tech or owner after the visit
- Hours from visit to send: unknown — treat as a leak until timed
- Tool: paper / email / Jobber / Housecall / ServiceTitan / other
- Follow-up after silent estimate: none scheduled

## 4. Named leaks (max 5)
{chr(10).join(leak_lines)}

## 5. The one workflow I would install first
{report.first_workflow}

## 6. Sprint offer (only after they read this)
$497/week to install that one workflow and hand them the keys.
{settings.sku_sprint}

---
Garrett Carrol · Garcar Enterprise · Grandview / Kopperl, TX · {settings.operator_email}
"""
    name = intake.owner or "there"
    sms = (
        f"Hey {name} — I’m Garrett in Grandview. I write the 48-hour map of where "
        f"Texas {intake.trade} shops in {intake.city} lose jobs after the lead hits. "
        f"First response gap is usually the money. $47, delivered to your email. "
        f"If the map is wrong you say so. {settings.storefront}"
    )
    return AuditPacket(
        markdown=md,
        outreach_sms=sms,
        sku_audit=settings.sku_audit,
        sku_sprint=settings.sku_sprint,
    )
