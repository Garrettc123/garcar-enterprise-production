# Autonomous Sales Fleet

Five agents. One job: **move attention into paid strangers.**

| Agent | Job |
|-------|-----|
| Scout | Source ICP leads (seed + optional Apollo + env paste) |
| Scorer | Rank by title / geo / email presence |
| Outreacher | Personalize Texas-trades copy |
| Closer | Attach live Stripe SKU link; optional Resend send |
| Watcher | Confirm `garcar-payments` edge is healthy (webhook path) |

## Run locally

```bash
# Dry-run (default) — generates outreach packets, does not send
PYTHONPATH=. python -m agents.sales_fleet.fleet --sku 47 --limit 10

# Live send (requires RESEND_API_KEY + real emails)
FLEET_DRY_RUN=false RESEND_API_KEY=re_... PYTHONPATH=. python -m agents.sales_fleet.fleet --sku 47 --live
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
| `FLEET_LEAD_JSON` | JSON array of leads |
| `GARCAR_PAYMENTS_URL` | Edge health check |

## Revenue path

```
Fleet outreach → stranger clicks SKU link → Stripe Checkout
  → /stripe-webhook (edge, signature verified, queue)
  → fulfillment job → entitlement + email
```

Webhook abort-on-missing-trace_id was fixed 2026-09-19. Cash can land.

## GitHub Action

`.github/workflows/sales-fleet.yml` runs on schedule + manual dispatch.
Default is dry-run. Set secrets + live input only when ready to send.
