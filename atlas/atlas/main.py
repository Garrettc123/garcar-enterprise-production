from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import settings
from .dry_run import analyze, write_map
from .schemas import ShopIntake


def run(intake: ShopIntake) -> dict:
    if settings.dry_run or not settings.openai_api_key:
        report = analyze(intake)
        packet = write_map(intake, report)
        mode = "dry_run"
        crew_raw = None
    else:
        from .crew import build_crew

        result = build_crew(intake).kickoff()
        report = analyze(intake)
        packet = write_map(intake, report)
        packet.markdown = str(result)
        mode = "crewai"
        crew_raw = str(result)

    out = {
        "mode": mode,
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
    (dest / f"{slug}-packet.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def cli() -> None:
    p = argparse.ArgumentParser(description="ATLAS CrewAI revenue workflow")
    p.add_argument("--shop", required=True)
    p.add_argument("--trade", required=True)
    p.add_argument("--city", required=True)
    p.add_argument("--owner", default="")
    p.add_argument("--ticket", type=int, default=4500)
    p.add_argument("--jobs-week", type=int, default=8)
    args = p.parse_args()
    intake = ShopIntake(
        shop=args.shop,
        trade=args.trade,
        city=args.city,
        owner=args.owner,
        ticket=args.ticket,
        jobs_week=args.jobs_week,
    )
    out = run(intake)
    print(json.dumps({k: v for k, v in out.items() if k != "markdown"}, indent=2))
    print("\n--- AUDIT MAP ---\n")
    print(out["markdown"])


if __name__ == "__main__":
    cli()
