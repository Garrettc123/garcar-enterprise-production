# Continuum Grid v1 — Full Ship Package
**GARCAR Enterprise · 2026-09-13**

This directory contains every artifact required to close the revenue loop for the Agent Reliability Audit business and to instrument the Continuum Grid.

## Contents

| Path | Purpose |
|------|---------|
| `sql/001_garcar_events.sql` | Universal event bus (run first in Supabase) |
| `sql/002_revenue_tables.sql` | prospects / audits / implementations / retainers |
| `edge-functions/stripe-webhook.ts` | Stripe → audits.status + event bus |
| `contracts/garcar_base_contract.py` | FastAPI sidecar (health/meta/metrics/events) |
| `bootstrap/bootstrap_garcar.py` | Auto-add manifest + contract to pilot repos |
| `methodology/GARCAR-Agent-Reliability-Framework.md` | Publishable audit methodology |
| `landing/index.html` | Agent Reliability landing page |
| `docs/privacy-policy.md` | Privacy policy draft |

## Execution Order (Do This)

### 1. Supabase (5 min)
```bash
# In Supabase SQL Editor, run in order:
# 1. 001_garcar_events.sql
# 2. 002_revenue_tables.sql
# Then enable Realtime on garcar_events if desired.
```

### 2. Stripe Webhook Edge Function
```bash
supabase functions deploy stripe-webhook --no-verify-jwt
# Set secrets:
# STRIPE_WEBHOOK_SECRET, STRIPE_SECRET_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
# Point Stripe dashboard webhook to the function URL for:
# checkout.session.completed, payment_intent.succeeded,
# customer.subscription.*
```

### 3. Bootstrap Pilot Repos (dry-run first)
```bash
export GITHUB_TOKEN=ghp_...
python bootstrap/bootstrap_garcar.py          # dry-run
python bootstrap/bootstrap_garcar.py --execute # creates draft PRs
```

### 4. Publish Methodology
- Commit methodology to this repo (already done).
- Attach the same file to every SOW.

### 5. Landing Page
- Deploy landing/index.html to GitHub Pages or Netlify/Vercel.
- Primary CTA: mailto or Stripe Checkout for the $2,500 audit.

### 6. Legal
- MSA + DPA + Privacy Policy ready for attorney final review.
- Do not take production data work until MSA + SOW are signed.

## Revenue Loop (once live)

```
Outbound → prospect record
→ Booking / Stripe Checkout
→ webhook flips audits.status = active
→ You deliver report + write deliverable_url
→ Follow-on SOW for Control Foundation
→ Retainer record + Stripe subscription
```

Every state lives in Supabase. No spreadsheets.

## RHNS Note
All reliability claims stay within the RHNS product statement:
> RHNS is not a claim of machine consciousness.
> It is a consciousness-inspired architecture for persistent goal management, self-monitoring, structured memory, verification, and bounded autonomous action.

## Owner
Garrett Carrol · GARCAR Enterprise LLC · Grandview / Alvarado, Texas  
garrett@gargar.ai
