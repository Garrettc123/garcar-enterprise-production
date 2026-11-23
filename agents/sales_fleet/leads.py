"""Read operator-supplied lead records and optional Apollo account research."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Optional

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
    source_id: str = ""
    email_verified: bool = False
    consent_basis: str = ""

    @property
    def eligible_for_outreach(self) -> bool:
        return bool(self.source_id and self.email_verified and usable_email(self.email or "")
                    and self.consent_basis in {"requested_contact", "existing_customer", "documented_opt_in"})

    def to_dict(self) -> dict:
        return asdict(self)


def field(row: dict, key: str) -> str:
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


def usable_email(value: str) -> bool:
    if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
        return False
    local, domain = value.lower().split("@")
    reserved = {"example.com", "example.org", "example.net", "email_not_unlocked.com"}
    return not (any(domain == item or domain.endswith("." + item) for item in reserved) or domain.endswith((".test", ".invalid", ".example", ".localhost", ".internal"))
                or (domain == "garcar.io" and local.startswith("atlas+")))


def load_env_leads() -> list[Lead]:
    raw = os.getenv("FLEET_LEAD_JSON", "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("FLEET_LEAD_JSON must contain an array of records")
    suppressed = {field(row, "email").lower() for row in data
                  if row.get("suppressed") or row.get("do_not_contact")}
    leads = []
    for row in data:
        company = field(row, "company")
        if not company or any(row.get(k) for k in ("synthetic", "is_test", "mock", "demo", "suppressed", "do_not_contact")):
            continue
        if field(row, "source").lower() in {"seed", "test", "mock", "demo", "synthetic", "fixture", "fake", "sample"}:
            continue
        email = field(row, "email").lower()
        if email and email in suppressed:
            continue
        source_id = field(row, "source_id") or field(row, "source_url")
        leads.append(Lead(
            company=company, contact_name=field(row, "contact_name") or field(row, "name"),
            email=email if usable_email(email) else None, title=field(row, "title"),
            vertical=field(row, "vertical"), city=field(row, "city"), source="env",
            consent_basis=field(row, "consent_basis").lower(),
            source_id=source_id, email_verified=field(row, "email_status").lower() == "verified",
        ))
    return leads


def fetch_apollo_leads(limit: int = 20) -> list[Lead]:
    key = os.getenv("APOLLO_API_KEY", "").strip()
    if not key or limit < 1:
        return []
    payload = {"person_titles": config.ICP_TITLES, "person_locations": ["Texas"],
               "q_organization_keyword_tags": config.ICP_VERTICALS, "page": 1, "per_page": min(limit, 100)}
    req = urllib.request.Request("https://api.apollo.io/api/v1/mixed_people/api_search",
                                 data=json.dumps(payload).encode(), method="POST",
                                 headers={"X-Api-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            people = json.load(resp)["people"]
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise RuntimeError("Apollo lead search unavailable") from exc
    if not isinstance(people, list):
        raise ValueError("Apollo returned an invalid list of people")
    leads = []
    for person in people:
        org = person.get("organization") or {}
        if field(org, "name") and field(person, "id"):
            leads.append(Lead(field(org, "name"), field(person, "first_name"), None,
                              field(person, "title"), field(org, "industry"), field(person, "city"),
                              "apollo", source_id=field(person, "id")))
    return leads


def source_leads(limit: int | None = None) -> list[Lead]:
    limit = config.MAX_LEADS_PER_RUN if limit is None else limit
    if limit <= 0:
        return []
    unique = []
    seen = set()
    def collect(records):
        for lead in records:
            identity = lead.email or lead.source_id or lead.contact_name.casefold()
            key = (lead.company.casefold(), identity)
            if key not in seen:
                seen.add(key)
                unique.append(lead)
                if len(unique) == limit:
                    break
    collect(load_env_leads())
    if len(unique) < limit:
        collect(fetch_apollo_leads(limit - len(unique)))
    return unique
