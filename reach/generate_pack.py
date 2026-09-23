#!/usr/bin/env python3
"""Generate tonight's SMS pack. Never sends. HUMAN_SEND_REQUIRED."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "queue.csv"
OUT = ROOT / f"pack-{date.today().isoformat()}.md"

DEFAULT_URL = "https://garrettc123.github.io/1"
FRAME = (
    "Hey{name_bit} — I’m Garrett in Grandview. 48-hour map of where Texas "
    "{trade} shops lose jobs after the lead hits. $47 to your email. "
    "If it’s wrong you say so. {url}"
)


def main() -> None:
    rows = list(csv.DictReader(QUEUE.open(encoding="utf-8")))
    lines = [
        f"# REACH pack {date.today().isoformat()}",
        "",
        "Gate: you send from your phone. Stop means stop.",
        "",
    ]
    for i, r in enumerate(rows, 1):
        name = (r.get("owner") or "").strip()
        name_bit = f" {name}" if name else ""
        trade = (r.get("trade") or "HVAC").strip()
        url = (r.get("url") or DEFAULT_URL).strip()
        phone = (r.get("phone") or "").strip()
        shop = (r.get("shop") or "").strip()
        sms = FRAME.format(name_bit=name_bit, trade=trade, url=url)
        lines.append(f"## {i}. {shop} — {phone}")
        lines.append(sms)
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(rows)} texts)")


if __name__ == "__main__":
    main()
