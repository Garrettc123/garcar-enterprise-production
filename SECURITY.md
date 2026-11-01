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
- API bearer token: API_BEARER_TOKEN stored in Vault KV; not injected through container environment.
- AWS SDK workload identity: task role, instance role, or OIDC federation.
- S3 bucket: S3_LEDGER_BUCKET.

No static AWS keys, Vault root token, fake provider credentials, or secret fallbacks are included.

## Immutable ledger requirements
Before accepting traffic, readiness verifies S3 Object Lock, bucket versioning, default COMPLIANCE retention, all four S3 Block Public Access flags, and default server-side encryption (AES256 or AWS KMS). Each event is written to a shared sequence with a previous-event hash, a conditional head update, and a unique event-ID reservation. A concurrent head conflict fails closed and requires manual reconciliation of the orphaned immutable event before writes resume.

## Runtime AWS permissions

Attach the managed policy created by `terraform/iam.tf` to the dedicated workload role used by the service. It grants only bucket-configuration reads, event-prefix listing, object reads/version reads/retention inspection, and object writes under `evidence/*`. It grants no object deletion, bucket creation, bucket-policy changes, retention configuration changes, or retention shortening. The caller must have `s3:GetObjectRetention` to inspect Object Lock metadata returned by object reads/HEAD requests. AWS documents that retention metadata is returned only when the requester has that permission.

S3 Object Lock COMPLIANCE retention is legally and operationally consequential. Terraform
bucket creation is disabled by default. Supply a retention period and explicitly enable
bucket creation only after legal, cost, and recovery review. Do not apply Terraform to a
production account as part of routine CI. The IAM policy is a separate managed policy; the
hosting platform must provide the trust relationship and attach it to the actual workload identity.

## Approval boundary
Every permit remains HUMAN_REVIEW_REQUIRED. Contractor rating and project history are
unknown unless a separately approved evidence provider supplies source records. Outreach
and financial actions are outside this service.

## Before production
Add rate limiting, audit monitoring, key rotation, integration tests against an isolated Object Lock bucket, restore/reconciliation drills, and an independently reviewed retention policy. CI passing alone does not establish production readiness.
