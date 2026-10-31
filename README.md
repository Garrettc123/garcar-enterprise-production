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

---

# Immutable Wealth Machine — guarded implementation

## Repository status
This branch contains a guarded implementation candidate. It is not a production deployment, compliance certification, live GraphRAG connection, or authorization for autonomous financial activity.

## Implemented foundation
- FastAPI permit-ingress endpoint.
- Vault-backed runtime secret retrieval with token or AWS IAM authentication.
- Fail-closed startup when Vault is required; production cannot disable Vault.
- Canonical JSON and SHA-256 ledger fingerprints.
- S3 writes request Object Lock Compliance retention and conditional create.
- Terraform provisions a versioned, private S3 bucket with Object Lock and KMS server-side encryption.
- Stripe webhook signature verification before payout-event recording.
- Payout records retain integer minor units and event identifiers.
- Permit decisions default to REVIEW_REQUIRED; no invented contractor ratings or automatic approval.
- Container runs non-root, read-only, with dropped Linux capabilities.
- CI runs unit tests, dependency audit and Terraform validation.

## Deliberately disabled
- GraphRAG provider connections and retrieval.
- Outbound email, SMS or customer outreach.
- Payout initiation, transfers or capital allocation.
- Autonomous approval of permits, contracts or payments.
- Production deployment and live customer traffic.

These require source-backed data, versioned policy definitions, idempotency/reconciliation tests, least-privilege cloud roles, monitoring, incident procedures and explicit release approval.

## Local checks
```bash
python -m pip install -r requirements.txt
pytest -q
python -m compileall -q src tests
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

## Production prerequisites
1. Provision a uniquely named S3 Object Lock bucket; Object Lock must be enabled at bucket creation.
2. Review and apply Terraform using an authorized AWS deployment identity.
3. Configure an IAM workload role restricted to the ledger bucket and encryption key.
4. Configure Vault AWS IAM auth or a short-lived Vault token and attach `vault/policies/app-policy.hcl`.
5. Store the Stripe endpoint signing secret at `secret/garcar/production/keys` as `STRIPE_WEBHOOK_SECRET`.
6. Set `S3_LEDGER_BUCKET`, `AWS_REGION`, `VAULT_ADDR`, and the selected Vault authentication settings in the runtime.
7. Test against isolated AWS and Stripe test resources, then verify alerting, backups, retention and incident response.
8. Require passing CI and a reviewed deployment plan before production traffic.

**No cloud resources are created by CI.** Terraform validation is not a Terraform apply. S3 Object Lock COMPLIANCE retention is intentionally irreversible for the configured retention window; review retention and legal requirements before provisioning.
