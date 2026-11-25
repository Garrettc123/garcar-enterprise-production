# Autonomous Sales Fleet

Five agents. One job: **move attention into paid strangers.**

| Agent | Job |
|-------|-----|
| Scout | Source only operator-supplied or Apollo leads (no synthetic fallback) |
| Scorer | Rank by title / geo / email presence |
| Outreacher | Personalize Texas-trades copy |
| Closer | Attach live Stripe SKU link; optional Resend send |
| Watcher | Confirm `garcar-payments` edge is healthy (webhook path) |

## Run locally

```bash
# Dry-run (default) — generates outreach packets, does not send
PYTHONPATH=. python -m agents.sales_fleet.fleet --sku 497 --limit 10

# Live send is intentionally approval-gated (GAR-530). Do not activate until
# contact verification, compliance review and recipient-bound approval are in place.
# FLEET_DRY_RUN=false also requires RESEND_API_KEY and FLEET_APPROVAL_ID.
```

## Env

| Var | Purpose |
|-----|---------|
| `FLEET_DRY_RUN` | `true` (default) or `false` |
| `FLEET_MAX_LEADS` | Cap per cycle (default 25) |
| `FLEET_MIN_SCORE` | Outreach threshold (default 55) |
| `GARCAR_DEFAULT_SKU` | `47` / `497` / `2500` |
| `RESEND_API_KEY` | Required for live email |
| `EMAIL_FROM` | Sender |
| `APOLLO_API_KEY` | Optional lead source |
| `FLEET_LEAD_JSON` | JSON array of real, authorized leads; no example fallback |
| `FLEET_SUPPRESSED_EMAILS` | Comma-separated additional blocked recipients |
| `FLEET_SUPPRESSED_DOMAINS` | Comma-separated additional blocked domains |
| `FLEET_APPROVAL_ID` | Recipient-bound approval identifier required for each live send |
| `GARCAR_PAYMENTS_URL` | Edge health check |

## Revenue path

```
Fleet outreach → stranger clicks SKU link → Stripe Checkout
  → /stripe-webhook (edge, signature verified, queue)
  → fulfillment job → entitlement + email
```

A reachable edge does not prove valid webhooks, paid charges, or fulfilled orders. Reconcile live Stripe charges and webhook delivery separately.

## GitHub Action

`.github/workflows/sales-fleet.yml` runs on schedule + manual dispatch.
Default is dry-run. Set secrets + live input only when ready to send.

## Deliverability and source integrity

No fabricated contact seed records are loaded. With no operator-supplied leads and no reachable authorized lead source, the fleet must return **zero leads**, not substitute example prospects. A known-delivery-failure suppression list is checked **before** a send approval or network call (nine unique recipients from late October–November 2026 Gmail failures; their hashes, not raw addresses, are tracked in `suppression.py`). Additional suppression lists can be provided through environment variables. Temporary delivery failures are held until re-verification. This protects only the `agents/sales_fleet` send path; external outbound tools must maintain their own suppression synchronization.

**Pre-send evidence requirement:** A syntactically valid address is not proof of opt-in, deliverability, or authorization. The existing GAR-530 recipient-bound approval remains mandatory. Do not interpret dry-run packets, sent messages, scheduled jobs, or delivered email as paid customers.

**Verification:** Run `pytest -q tests/test_sales_fleet_deliverability.py tests/test_gated_call_sites.py`. If CI is unavailable, tests remain *unverified* until they execute successfully in a controlled environment.
