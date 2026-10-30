# Garcar Enterprise — Live Offer

**Buyer:** real-estate team leads  
**Product:** backup rules around the CRM they already use so new leads get called  
**Price:** $2,500 one time, three business days  
**Fallback:** $497 lead-export review, credited to the $2,500

Page: https://garrettc123.github.io/  
One-pager: https://garrettc123.github.io/overview.html  
Call script: `CASH_COMMAND.md`

Do not sell MARS, AI, or automation on the phone. Sell: new leads get called back before they go somewhere else.

Payment link is sent after they give an email and say start. There is no $2,500 button on the page until that Stripe link exists.

Canonical checkout webhook: `https://garcar-payments.garrettc123.workers.dev/stripe-webhook`

## Revenue recovery context (2026-10-24)

- Company domain `garcar.io` was unregistered (NXDOMAIN) at the time of the recorded check.
- Operational and customer contact was routed to the verified inbox `gwc2780@gmail.com`.
- Active revenue path: $497 review → $2,500 install. Other offers, case-study claims, and unproven feeds were on hold pending a source-backed sample and one completed delivery.
- Stripe account had a negative balance and payout-method verification was pending at the time of the recorded check.
- Historical test-card attempts must not be treated as current payment-health failures.

## Founder

Garrett Carrol · Grandview / Kopperl, TX

---

# Garcar Enterprise — Immutable Wealth Machine

This repository is the guarded implementation baseline for the Garcar Enterprise control plane. It is not a claim of production deployment, compliance certification, live GraphRAG, or autonomous financial authority.

## Security posture
- Vault authentication is required by default. No dev token, mock secret, or silent environment fallback is accepted.
- AWS credentials use the standard AWS credential provider chain (for example, an IAM role); do not store AWS access keys in application configuration.
- Ledger records are canonicalized, SHA-256 fingerprinted, and written with explicit S3 Object Lock Compliance retention.
- Permit intake fails closed when the ledger is unavailable.
- Permit evaluation defaults to REVIEW_REQUIRED. No fabricated ratings, project counts, or automatic approval.
- Stripe webhooks require signature verification. Payout events are recorded; this service does not initiate payouts.
- CI tests, dependency audit, and Terraform validation run on pushes and pull requests.

## Local development
Set non-production test credentials in your shell and configure a test S3 Object Lock bucket. Install dependencies with `pip install -r requirements.txt`; run `pytest -q`; start with `uvicorn src.main:app --reload`.

## Required production prerequisites
1. Create a unique S3 bucket with Object Lock enabled at creation, versioning, public access blocks, and KMS encryption.
2. Configure an IAM workload role restricted to the ledger bucket and required KMS key.
3. Configure Vault workload authentication and attach `vault/policies/app-policy.hcl`; do not use a root token.
4. Provision the Stripe webhook signing secret in Vault and verify the endpoint with Stripe test events.
5. Set the actual bucket, AWS region, retention policy, and webhook configuration through the deployment environment.
6. Run Terraform plan and review its destructive-change report before apply.
7. Run CI and integration tests against isolated AWS/Stripe test resources before any production traffic.

## Explicitly not enabled
GraphRAG retrieval, outbound email, customer messaging, payout initiation, autonomous capital allocation, and production deployment remain disabled until their data sources, policies, tests, and authorization gates are implemented and independently verified.
