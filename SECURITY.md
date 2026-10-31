# Security and operational boundaries

## Current scope
This repository implements authenticated evidence intake and review preparation only.
It does not send contractor outreach, approve contractors, initiate Stripe payouts,
or deploy cloud infrastructure.

## Required runtime configuration
- Vault AppRole: VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID.
- Vault KV v2 path: secret/data/garcar/production/keys (mount/path configurable).
- Vault public approval key: OWNER_APPROVAL_PUBLIC_KEY (private signing key stays offline).
- Vault Stripe webhook secret: STRIPE_WEBHOOK_SECRET.
- API bearer token: API_BEARER_TOKEN.
- AWS SDK workload identity: task role, instance role, or OIDC federation.
- S3 bucket: S3_LEDGER_BUCKET.

No static AWS keys, Vault root token, fake provider credentials, or secret fallbacks are included.

## Immutable ledger requirements
Before writing an event, the service verifies S3 Object Lock is enabled, bucket versioning
is enabled, and default retention mode is COMPLIANCE. Each event is written to a shared sequence with a previous-event hash, a conditional head update,
and a unique event-ID reservation. A concurrent head conflict fails closed and requires manual
reconciliation of the orphaned immutable event before writes resume.

S3 Object Lock COMPLIANCE retention is legally and operationally consequential. Terraform
bucket creation is disabled by default. Supply a retention period and explicitly enable
bucket creation only after legal, cost, and recovery review. Do not apply Terraform to a
production account as part of routine CI.

## Approval boundary
Every permit remains HUMAN_REVIEW_REQUIRED. Contractor rating and project history are
unknown unless a separately approved evidence provider supplies source records. Outreach
and financial actions are outside this service.

## Before production
Add authenticated ingress controls, rate limiting, audit monitoring, key rotation,
integration tests against an isolated Object Lock bucket, restore/reconciliation drills,
and an independently reviewed retention policy. CI passing alone does not establish
production readiness.
