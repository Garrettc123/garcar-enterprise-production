from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import settings
from .dry_run import analyze, write_map
from .router import Route, route_with_agent, select_route
from .schemas import ShopIntake


def run(
    intake: ShopIntake,
    sku: str | None = None,
    force_route: str | None = None,
    use_agent_router: bool = False,
) -> dict:
    if force_route:
        decision = select_route(intake, sku=sku, force=force_route)
    elif use_agent_router:
        decision = route_with_agent(intake, sku=sku)
    else:
        decision = select_route(intake, sku=sku)

    if settings.dry_run or not settings.openai_api_key:
        report = analyze(intake)
        packet = write_map(intake, report)
        sms = packet.outreach_sms
        if decision.storefront_url and decision.route != Route.REJECT:
            if "http" in sms:
                idx = sms.rfind("http")
                if idx >= 0:
                    sms = sms[:idx].rstrip() + " " + decision.storefront_url
                else:
                    sms = f"{sms} {decision.storefront_url}"
            else:
                sms = f"{sms} {decision.storefront_url}"
        packet.outreach_sms = sms
        mode = "dry_run"
        crew_raw = None
    else:
        from .crew import build_crew

        result = build_crew(intake, decision).kickoff()
        report = analyze(intake)
        packet = write_map(intake, report)
        packet.markdown = str(result)
        mode = "crewai"
        crew_raw = str(result)

    out = {
        "mode": mode,
        "route": decision.route.value,
        "route_reason": decision.reason,
        "route_source": decision.source,
        "route_sku": decision.sku,
        "storefront_url": decision.storefront_url,
        "gate": packet.gate,
        "sku_audit": packet.sku_audit,
        "sku_sprint": packet.sku_sprint,
        "outreach_sms": packet.outreach_sms,
        "monthly_leak_total": report.monthly_leak_total,
        "first_workflow": report.first_workflow,
        "markdown": packet.markdown,
        "crew_raw": crew_raw,
    }
    dest = Path("output")
    dest.mkdir(exist_ok=True)
    slug = intake.shop.lower().replace(" ", "-")
    (dest / f"{slug}-audit.md").write_text(packet.markdown, encoding="utf-8")
    (dest / f"{slug}-packet.json").write_text(
        json.dumps({k: v for k, v in out.items() if k != "markdown"}, indent=2),
        encoding="utf-8",
    )
    return out


def cli() -> None:
    p = argparse.ArgumentParser(description="ATLAS CrewAI revenue workflow + router")
    p.add_argument("--shop", required=True)
    p.add_argument("--trade", required=True)
    p.add_argument("--city", required=True)
    p.add_argument("--owner", default="")
    p.add_argument("--ticket", type=int, default=4500)
    p.add_argument("--jobs-week", type=int, default=8)
    p.add_argument("--sku", default="", help="47-audit | 497-week | 497-re | 2500-re | atlas")
    p.add_argument(
        "--route",
        default="",
        help="Force: trades_47 | trades_sprint | re_497 | re_2500 | atlas_custom | reject",
    )
    p.add_argument(
        "--agent-router",
        action="store_true",
        help="Allow LLM router agent when rules are ambiguous",
    )
    args = p.parse_args()
    intake = ShopIntake(
        shop=args.shop,
        trade=args.trade,
        city=args.city,
        owner=args.owner,
        ticket=args.ticket,
        jobs_week=args.jobs_week,
    )
    out = run(
        intake,
        sku=args.sku or None,
        force_route=args.route or None,
        use_agent_router=args.agent_router,
    )
    print(
        json.dumps(
            {k: v for k, v in out.items() if k not in {"markdown", "crew_raw"}},
            indent=2,
        )
    )
    print("\n--- AUDIT MAP ---\n")
    print(out["markdown"])


if __name__ == "__main__":
    cli()
