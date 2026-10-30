# Garcar Enterprise — Live Offer

**Buyer:** real-estate team leads  
**Product:** backup rules around the CRM they already use so new leads get called  
**Price:** $2,500 one time, three business days  
**Fallback:** $497 lead-export review, credited to the $2,500

**LLA-47 wedge (trades):** $47 lead-loss map — https://buy.stripe.com/3cI00j7YV0hQgDp8BR43S2v

Page: https://garrettc123.github.io/  
One-pager to send after a call: https://garrettc123.github.io/overview.html  
Call script: `CASH_COMMAND.md`

Do not sell MARS, AI, or automation on the phone.
Sell: new leads get called back before they go somewhere else.

Payment link is sent after they give an email and say start. There is no $2,500 button on the page until that Stripe link exists.

Canonical checkout webhook (for any live Payment Link that does fire): `https://garcar-payments.garrettc123.workers.dev/stripe-webhook`

## Recovery Status (2026-10-24)

Company domain `garcar.io` is unregistered (NXDOMAIN). All operational and customer contact is routed exclusively to the verified inbox `gwc2780@gmail.com`.

Active revenue path is the $497 review → $2,500 install only. All other offers, case-study claims, and unproven feeds are on hold until a source-backed sample and one completed delivery exist.

Stripe account has a negative balance; payout method verification is pending. Automation gates that stop on historical test-card attempts must be scoped to current health checks only.

## Founder

Garrett Carrol · gwc2780@gmail.com · Grandview / Kopperl, TX

---

## Production Gateway (synced 2026-10-30)

Zero-human DFW permit lead orchestrator:

- `src/main.py` — FastAPI + LangGraph 1.2.19
  - Vault / env secrets
  - S3 WORM ledger (SHA-256)
  - GraphRAG enrichment (stub)
  - RHNS guardrails (< $75k + rating ≥ 4.0 auto-approve)
  - Outreach draft with LLA-47 payment link
  - `GET /health` + `POST /webhook/permits/dfw`
- `terraform/main.tf` — S3 Object Lock (COMPLIANCE, 1 year)
- `Dockerfile` + `docker-compose.yml`
- `.github/workflows/gateway-ci.yml` — smoke CI
- `vault/policies/garcar-gateway.hcl`

### Quick start
```bash
export STRIPE_SECRET_KEY=sk_...
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
docker compose up --build -d
curl http://localhost:8000/health
```

Apply Terraform before S3 writes. GraphRAG is a stub until wired to real contractor data.

Revenue loop: permit → ledger → qualify → outreach with live payment link → Stripe close.
