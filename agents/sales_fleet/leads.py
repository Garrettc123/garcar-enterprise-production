"""Lead source for the Sales Fleet.

Uses:
1. Seed ICP list (always available — no key required)
2. Optional Apollo when APOLLO_API_KEY is set
3. Optional env FLEET_LEAD_JSON for operator-pasted lists
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import List, Optional

from . import config


@dataclass
class Lead:
    company: str
    contact_name: str
    email: Optional[str]
    title: str
    vertical: str
    city: str
    source: str
    score: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Seed ICP — DFW / North Texas trades. Expand via Apollo or paste list.
SEED_LEADS: List[Lead] = [
    Lead("Summit Roofing TX", "Marcus", None, "Owner", "roofing", "Fort Worth", "seed"),
    Lead("Bluebonnet HVAC", "Elena", None, "Owner", "HVAC", "Arlington", "seed"),
    Lead("Lone Star Plumbing Co", "Derek", None, "President", "plumbing", "Dallas", "seed"),
    Lead("Cleburne Electric Pros", "James", None, "Founder", "electrical", "Cleburne", "seed"),
    Lead("Grandview GC Partners", "Ryan", None, "Principal", "general contractor", "Grandview", "seed"),
    Lead("DFW Air & Heat", "Sofia", None, "GM", "HVAC", "Irving", "seed"),
    Lead("Trinity Valley Roofing", "Chris", None, "Owner", "roofing", "Waxahachie", "seed"),
    Lead("North Texas Drain & Pipe", "Luis", None, "Owner", "plumbing", "Denton", "seed"),
    Lead("Metroplex Build Group", "Amanda", None, "VP Operations", "general contractor", "Plano", "seed"),
    Lead("Hill Country HVAC South", "Kevin", None, "Owner", "HVAC", "Burleson", "seed"),
]


def load_env_leads() -> List[Lead]:
    raw = os.getenv("FLEET_LEAD_JSON", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: List[Lead] = []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        out.append(
            Lead(
                company=str(row.get("company") or "Unknown"),
                contact_name=str(row.get("contact_name") or row.get("name") or "there"),
                email=row.get("email"),
                title=str(row.get("title") or "Owner"),
                vertical=str(row.get("vertical") or "HVAC"),
                city=str(row.get("city") or "DFW"),
                source="env",
            )
        )
    return out


def fetch_apollo_leads(limit: int = 20) -> List[Lead]:
    api_key = os.getenv("APOLLO_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        import requests
    except ImportError:
        return []
    url = "https://api.apollo.io/v1/mixed_people/search"
    payload = {
        "q_organization_keyword_tags": ["HVAC", "roofing", "plumbing", "general contractor"],
        "person_titles": config.ICP_TITLES,
        "person_locations": ["Texas", "Dallas", "Fort Worth"],
        "page": 1,
        "per_page": min(limit, 25),
    }
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code >= 400:
            return []
        people = (r.json() or {}).get("people") or []
    except Exception:
        return []
    out: List[Lead] = []
    for p in people:
        org = p.get("organization") or {}
        email = p.get("email")
        if email and str(email).endswith("email_not_unlocked.com"):
            email = None
        out.append(
            Lead(
                company=str(org.get("name") or "Unknown Co"),
                contact_name=str(
                    (p.get("first_name") or "") + " " + (p.get("last_name") or "")
                ).strip()
                or "there",
                email=email,
                title=str(p.get("title") or "Owner"),
                vertical=_guess_vertical(org.get("name") or "", p.get("headline") or ""),
                city=str((p.get("city") or org.get("city") or "Texas")),
                source="apollo",
            )
        )
    return out


def _guess_vertical(name: str, headline: str) -> str:
    blob = f"{name} {headline}".lower()
    for v in config.ICP_VERTICALS:
        if v.lower() in blob:
            return v
    return "HVAC"


def source_leads(limit: int | None = None) -> List[Lead]:
    limit = limit or config.MAX_LEADS_PER_RUN
    leads: List[Lead] = []
    leads.extend(load_env_leads())
    leads.extend(fetch_apollo_leads(limit=limit))
    if len(leads) < limit:
        leads.extend(SEED_LEADS)
    seen = set()
    unique: List[Lead] = []
    for lead in leads:
        key = (lead.company.lower().strip(), lead.contact_name.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append(lead)
        if len(unique) >= limit:
            break
    return unique
