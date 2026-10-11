#!/usr/bin/env python3
"""
Garcar Enterprise — Non-Simulated Production Grid
Stripe Charge Reconciliation → Supabase durable_events → HubSpot → Notion

Requires host environment variables (never commit):
  STRIPE_SECRET_KEY
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  HUBSPOT_ACCESS_TOKEN
  NOTION_API_KEY
  NOTION_DATABASE_ID
  ENVIRONMENT (default: staging)

Install: pip install stripe supabase requests
"""

import os
import sys
import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import stripe
    from supabase import create_client, Client
    import requests
except ImportError as e:
    print(f"Missing dependency: {e}. Run: pip install stripe supabase requests", file=sys.stderr)
    sys.exit(1)


def get_env_var(name: str, required: bool = True) -> Optional[str]:
    val = os.environ.get(name)
    if required and not val:
        raise ValueError(f"Missing mandatory environment credential: {name}")
    return val


def payload_hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def hubspot_upsert_contact(email: str, name: Optional[str], headers: dict) -> Optional[str]:
    """Search then create/update contact. Returns contact id or None."""
    search_payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            }]
        }],
        "properties": ["email", "firstname"],
        "limit": 1
    }
    try:
        r = requests.post(
            "https://api.hubapi.com/crm/v3/objects/contacts/search",
            headers=headers,
            json=search_payload,
            timeout=15
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return results[0]["id"]
    except Exception as e:
        print(f"HubSpot search failed for {email}: {e}")

    # Create
    contact_payload = {
        "properties": {
            "email": email,
            "firstname": name or "Customer",
            "lifecyclestage": "customer"
        }
    }
    try:
        r = requests.post(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers=headers,
            json=contact_payload,
            timeout=15
        )
        if r.status_code in (200, 201):
            return r.json().get("id")
        print(f"HubSpot contact create failed ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"HubSpot contact create exception: {e}")
    return None


def hubspot_create_deal(charge_id: str, amount_usd: float, email: str, contact_id: Optional[str], headers: dict) -> None:
    deal_payload = {
        "properties": {
            "dealname": f"Enterprise Checkout - {charge_id}",
            "amount": str(amount_usd),
            "dealstage": "closedwon",
            "pipeline": "default"
        }
    }
    if contact_id:
        deal_payload["associations"] = [{
            "to": {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
        }]
    try:
        r = requests.post(
            "https://api.hubapi.com/crm/v3/objects/deals",
            headers=headers,
            json=deal_payload,
            timeout=15
        )
        if r.status_code not in (200, 201):
            print(f"HubSpot deal create failed ({r.status_code}): {r.text[:200]}")
        else:
            print(f"HubSpot deal created for {email} / {charge_id}")
    except Exception as e:
        print(f"HubSpot deal exception: {e}")


def notion_ledger_entry(event_key: str, amount: float, paid: bool, created_iso: str, headers: dict, db_id: str) -> None:
    notion_page = {
        "parent": {"database_id": db_id},
        "properties": {
            "Event Key": {"title": [{"text": {"content": event_key}}]},
            "Amount": {"number": amount},
            "Status": {"select": {"name": "Processed" if paid else "Failed"}},
            "Provider": {"select": {"name": "Stripe"}},
            "Timestamp": {"date": {"start": created_iso}}
        }
    }
    try:
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=notion_page,
            timeout=15
        )
        if r.status_code not in (200, 201):
            print(f"Notion page create failed ({r.status_code}): {r.text[:200]}")
        else:
            print(f"Notion ledger entry created for {event_key}")
    except Exception as e:
        print(f"Notion exception: {e}")


def run_non_simulated_pipeline():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Non-Simulated Garcar Enterprise Production Grid...")

    stripe_key = get_env_var("STRIPE_SECRET_KEY")
    supabase_url = get_env_var("SUPABASE_URL")
    supabase_key = get_env_var("SUPABASE_SERVICE_ROLE_KEY")
    hubspot_token = get_env_var("HUBSPOT_ACCESS_TOKEN")
    notion_key = get_env_var("NOTION_API_KEY")
    notion_db = get_env_var("NOTION_DATABASE_ID")
    env = get_env_var("ENVIRONMENT", required=False) or "staging"

    print(f"Operational Mode: {env.upper()}")

    print("Connecting to live Supabase cluster...")
    sb_client: Client = create_client(supabase_url, supabase_key)

    print("Connecting to Stripe Live API...")
    stripe.api_key = stripe_key

    hs_headers = {
        "Authorization": f"Bearer {hubspot_token}",
        "Content-Type": "application/json"
    }
    notion_headers = {
        "Authorization": f"Bearer {notion_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # Paginate charges (limit 100 per page, max ~500 for safety)
    starting_after = None
    total_processed = 0
    total_new = 0
    max_pages = 5

    for page in range(max_pages):
        params = {"limit": 100}
        if starting_after:
            params["starting_after"] = starting_after

        try:
            charges = stripe.Charge.list(**params)
        except Exception as e:
            print(f"Stripe Charge.list failed: {e}", file=sys.stderr)
            break

        print(f"Page {page + 1}: retrieved {len(charges.data)} charges")

        if not charges.data:
            break

        for ch in charges.data:
            total_processed += 1
            event_key = f"stripe:charge:{ch.id}"
            ch_dict = ch.to_dict() if hasattr(ch, "to_dict") else dict(ch)
            p_hash = payload_hash(ch_dict)

            # Exact-once check
            try:
                existing = sb_client.table("durable_events").select("event_key").eq("event_key", event_key).execute()
                if existing.data:
                    print(f"Durable event {event_key} already recorded. Skipping.")
                    continue
            except Exception as e:
                print(f"Supabase lookup failed for {event_key}: {e}")
                continue

            paid = bool(ch.paid)
            amount_usd = ch.amount / 100.0
            created_iso = datetime.fromtimestamp(ch.created, timezone.utc).isoformat()

            new_event = {
                "event_key": event_key,
                "provider": "stripe",
                "event_type": "charge.succeeded" if paid else "charge.failed",
                "provider_event_id": ch.id,
                "environment": env,
                "occurred_at": created_iso,
                "payload_hash": p_hash,
                "trace_id": ch.id,
                "status": "processed" if paid else "failed",
                "duplicate_count": 0
            }

            try:
                sb_client.table("durable_events").insert(new_event).execute()
                total_new += 1
                print(f"Recorded {event_key} (${amount_usd:.2f} {ch.currency.upper()}) paid={paid}")
            except Exception as e:
                print(f"Supabase insert failed for {event_key}: {e}")
                continue

            # HubSpot sync only for paid with email
            billing = getattr(ch, "billing_details", None) or {}
            email = billing.get("email") if isinstance(billing, dict) else getattr(billing, "email", None)
            name = billing.get("name") if isinstance(billing, dict) else getattr(billing, "name", None)

            if paid and email:
                contact_id = hubspot_upsert_contact(email, name, hs_headers)
                hubspot_create_deal(ch.id, amount_usd, email, contact_id, hs_headers)

            # Notion ledger (all charges)
            notion_ledger_entry(event_key, amount_usd, paid, created_iso, notion_headers, notion_db)

            # Light rate limit
            time.sleep(0.2)

        if not charges.has_more:
            break
        starting_after = charges.data[-1].id

    print(f"Cycle complete. Processed: {total_processed}, New durable events: {total_new}")
    print("Non-simulated synchronization cycle completed.")


if __name__ == "__main__":
    try:
        run_non_simulated_pipeline()
    except Exception as e:
        print(f"Execution halted: {e}", file=sys.stderr)
        sys.exit(1)
