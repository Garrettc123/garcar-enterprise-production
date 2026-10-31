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

## Guarded Evidence Gateway

This repository contains a **guarded implementation**, not a claim of production deployment. The API records submitted evidence and prepares human-review records. It does not automatically approve contractors, send outreach, or initiate financial actions.

- FastAPI permit intake with strict payload validation.
- Vault AppRole authentication with fail-closed behavior and credentials loaded from Vault.
- AWS SDK workload identity; no hardcoded AWS credentials.
- S3 Object Lock preflight and per-version COMPLIANCE retention verification.
- Append-only SHA-256 event chain for permit intake, owner approvals, and Stripe event metadata.
- RHNS policy gate that rejects missing source evidence, authority, budget, or owner approval.
- Ed25519 approval verification using a public key; the private signing key stays offline.
- Stripe webhook signature verification; event metadata is recorded only. No charge, refund, transfer, or payout is performed.

### Runtime configuration

Container environment variables are limited to Vault AppRole connection values and non-secret platform settings:

- `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`
- `VAULT_KV_PATH=garcar/production/keys`, `VAULT_MOUNT=secret`
- `AWS_REGION`, `S3_LEDGER_BUCKET`

Vault KV v2 must contain `API_BEARER_TOKEN`, `OWNER_APPROVAL_PUBLIC_KEY`, `STRIPE_WEBHOOK_SECRET`, and `S3_LEDGER_BUCKET`. The AWS runtime identity must be authorized for the configured bucket. Do not place secrets in source control, README files, or chat.

### Local container

```bash
# Configure the Vault connection and non-secret settings in your deployment secret manager.
docker compose up --build
```

The container listens on `PORT` (default 8000). `/live` reports process liveness. `/health` reports readiness only when Vault and the S3 Object Lock configuration are reachable and verified.

### Production status and gates

The repository code is **not a production deployment by itself**. Before enabling production traffic, an owner must configure Vault AppRole access, the AWS workload identity, and an existing S3 bucket with versioning and COMPLIANCE retention. Terraform bucket creation is disabled by default because COMPLIANCE retention is difficult or impossible to shorten or remove for retained objects. Run the application tests, Terraform validation, S3 concurrency/recovery tests, and security review before release.

GraphRAG enrichment is deliberately a no-data default until a real source provider is connected. Missing contractor ratings, project counts, or permit evidence remain unknown; no fabricated scores are used.
