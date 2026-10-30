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
