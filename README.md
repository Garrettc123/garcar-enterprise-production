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

# Immutable Wealth Machine — guarded release candidate

## Repository and deployment status

This branch contains a guarded FastAPI implementation and supporting ledger, payout-evidence, policy, and test modules. It is a **release candidate, not a production deployment**, compliance certification, live GraphRAG connection, or authorization for autonomous financial activity.

The permit intake and owner-approval routes are authenticated. Stripe webhook routes require Stripe signature verification. The service records evidence; it does not initiate payouts, transfers, charges, refunds, email, SMS, or customer outreach.

## Implemented controls

- Vault AppRole authentication; API bearer token, Stripe webhook secret, and owner public key are loaded from Vault KV v2. Missing Vault configuration fails closed.
- AWS SDK default credential chain for workload identity; no static AWS keys or development credential fallbacks.
- Private S3 bucket configuration with versioning, all four public-access blocks, AES256 server-side encryption, and Object Lock COMPLIANCE retention. Readiness checks verify each of these controls. Terraform bucket creation is disabled by default and protected from destruction.
- Least-privilege runtime IAM managed policy in `terraform/iam.tf`; it permits only event, reservation, and receipt prefix listing, object read/version/retention inspection, object writes, and required bucket-configuration reads. It grants no delete or bucket/retention administration.
- Append-only SHA-256 event chain for permit intake, signed owner approvals, and Stripe event evidence. Immutable idempotency reservations and completion receipts allow identical retries to reuse the original hash while rejecting changed payloads.
- Ed25519 approval signatures scoped to a permit, validity window, evidence references, and limited review/export actions. The verified public signature is stored with the immutable approval record; the application never receives the private signing key.
- Deterministic evidence-first RHNS policy. Missing source records, identity, authority, budget, or approval keep permits in human review.
- Stripe webhook signature verification. Verified `payout.paid` events retain payout ID, amount in integer minor units, currency, event ID, and status. This records a Stripe event only; it does not initiate a payout or independently establish that funds reached a bank.
- Docker runs as a non-root user, uses a read-only root filesystem in Compose, has dropped Linux capabilities, uses a separate liveness endpoint, and runs one application worker.
- A ledger verifier follows the event hash referenced by the chain head, checks every reservation and completion receipt, and flags unlinked or incomplete immutable writes for manual reconciliation.

## Runtime configuration

Container environment variables:

- `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`
- `VAULT_KV_PATH=garcar/production/keys`, `VAULT_MOUNT=secret`
- `AWS_REGION`, `S3_LEDGER_BUCKET`

Vault KV v2 must contain:

- `API_BEARER_TOKEN` — at least 32 characters; generate locally with `python scripts/generate_api_token.py`.
- `OWNER_APPROVAL_PUBLIC_KEY` — base64-encoded raw Ed25519 public key (exactly 32 decoded bytes); generate locally with `python scripts/generate_owner_keypair.py`.
- `STRIPE_WEBHOOK_SECRET` — Stripe signing secret beginning with `whsec_`.
- `S3_LEDGER_BUCKET`.

The application validates these formats before reporting readiness. Keep generated tokens and private signing keys in a trusted local environment and Vault; never commit or paste them.

The runtime AWS identity must use the managed policy in `terraform/iam.tf`, attached to a dedicated workload role whose trust relationship is configured by the chosen hosting platform. This policy includes `s3:GetObjectRetention`, required to inspect Object Lock retention metadata returned by object requests. Do not put credentials in source control, README files, PR comments, or chat.

## Local container

Configure Vault AppRole values and non-secret settings in your deployment secret manager, then run:

```bash
docker compose up --build
```

Run `python scripts/production_preflight.py` from a trusted checkout after configuring Vault and AWS workload identity; it checks Vault value formats and S3 security settings without printing secrets or changing cloud resources. The container listens on `PORT` (default 8000). `/live` reports process liveness. `/health` reports readiness only when Vault is reachable and S3 Object Lock, versioning, default COMPLIANCE retention, all four public-access blocks, and server-side encryption are verified.

## Verification commands

```bash
python -m pip install -r requirements-dev.txt
ruff check src tests
pytest -q
python -m compileall -q src tests
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

A passing unit suite or Terraform validation does not prove the AWS integration, concurrency, recovery, deployment, or payout path is production-ready.

## Production prerequisites

1. Review the exact S3 bucket name, AWS account, region, and COMPLIANCE retention period. Object Lock COMPLIANCE retention is difficult or impossible to shorten for retained objects.
2. Provision or validate a dedicated versioned S3 Object Lock bucket and narrowly scoped AWS workload identity. Terraform bucket creation remains opt-in.
3. Configure Vault AppRole and KV values through approved secret-management controls.
4. Run all CI checks and review the actual runner logs. Test writes, duplicate requests, concurrent writers, interrupted writes, and recovery against an isolated Object Lock bucket.
5. Reconcile every unlinked event object before treating the ledger as clean.
6. Independently verify Stripe webhook delivery and compare Stripe payout records with bank settlement records. A `payout.paid` webhook is not proof of bank credit.
7. Complete rate limiting, monitoring, alerting, key rotation, backup/restore drills, incident procedures, and an independent security review.
8. Deploy only to a dedicated, cost-approved service after the release gates pass.

**No production service is created or deployed by this repository or its CI.** No AWS bucket has been created, no COMPLIANCE retention has been applied, no production secret has been changed, and no payment or payout action has been performed in this work.
