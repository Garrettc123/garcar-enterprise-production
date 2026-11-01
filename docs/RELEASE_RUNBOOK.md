# Production Release Runbook

## 1. Release state

The guarded gateway is a release candidate, not a production service. Keep PR #34 in draft until every gate below is verified. Do not disable required checks or merge to make the red checks disappear.

## 2. GitHub Actions runner recovery

The failed workflow runs observed on October 31, 2026 show jobs with:
- `runner_id: 0`
- empty `runner_name`
- zero recorded steps
- completion approximately 2–3 seconds after job creation
- job-log downloads returning `BlobNotFound`

A minimal diagnostic was added with only one `ubuntu-latest` job, no checkout, no third-party actions, no dependencies, and no secrets. It failed identically on both trigger types:
- Push run [41256370677](https://github.com/Garrettc123/garcar-enterprise-production/actions/runs/41256370677), job `124700282342`: runner ID 0, empty runner name, zero steps.
- Pull-request run [41256373772](https://github.com/Garrettc123/garcar-enterprise-production/actions/runs/41256373772), job `124700290915`: runner ID 0, empty runner name, zero steps.

This isolates the immediate failure from project dependencies and test commands: GitHub did not allocate a hosted runner even for the minimal shell-only probe. It is not evidence that pytest, Ruff, CodeQL, dependency audit, or Terraform ran and failed. The exact backend cause remains unknown.

The signature is also reported by other repositories in GitHub Community discussions, including [#211408](https://github.com/orgs/community/discussions/211408) (October 27, 2026) and [#209031](https://github.com/orgs/community/discussions/209031) (September 28, 2026). Those are corroborating reports, not proof of this account's root cause. GitHub's public status page showed Actions operational and no incident on October 31, 2026; that does not establish that this repository/account can allocate runners.

Operator checks:
1. Open repository Settings → Actions → General and confirm Actions are enabled for the repository.
2. Confirm the repository is allowed to use GitHub-hosted runners and the required standard runner image (`ubuntu-latest`).
3. Check account/repository Actions policy and whether GitHub-hosted standard runners are permitted for this repository. Do not assume an account restriction without the setting or GitHub error proving it.
4. This repository is public and the probe uses standard `ubuntu-latest`; GitHub documents standard hosted runners as free and unlimited for public repositories. Monthly included-minute exhaustion is therefore not the likely explanation for these jobs. Billing becomes relevant only if the repository visibility or runner class changes (for example, a paid larger runner).
5. Confirm workflow files are enabled and that the PR branch is not excluded by Actions policy.
6. Re-run the failed workflows only after runner allocation is restored.
7. Verify that each job has a nonzero runner ID, a runner name, executed steps, and downloadable logs.

Current public GitHub status should be checked separately; a green status page does not prove that this repository/account can allocate its own jobs. Do not attribute a repository-specific runner failure to a platform incident without a matching incident window.

## 3. CI gates

All of these must pass on the exact PR head SHA:
- ADM CI: backend compile and import smoke test.
- Garcar Gateway CI: gateway install, compile and import.
- CI Security Gate: unit tests, dependency audit and Terraform validation.
- garcar-guarded-ci: Ruff, pytest and Terraform formatting/validation.
- CodeQL: completed security analysis.

Review the actual logs, not only the top-level check labels. Keep the PR in draft if a run has no runner or step records.

## 4. Vault setup

Configure these platform variables only through the approved hosting secret manager:
- `VAULT_ADDR`
- `VAULT_ROLE_ID`
- `VAULT_SECRET_ID`

Vault KV v2 at `secret/garcar/production/keys` must contain:
- `API_BEARER_TOKEN`: at least 32 characters. Generate locally with `python scripts/generate_api_token.py`.
- `OWNER_APPROVAL_PUBLIC_KEY`: base64-encoded raw Ed25519 public key (32 decoded bytes). Generate locally with `python scripts/generate_owner_keypair.py`; keep the private key offline.
- `STRIPE_WEBHOOK_SECRET`: the Stripe endpoint signing secret beginning with `whsec_`.
- `S3_LEDGER_BUCKET`: the exact bucket name used by the service.

Never put the token, Vault SecretID, Stripe signing secret, or private key in source control, PR comments, or chat.

## 5. AWS workload identity and S3

Attach the policy created by `terraform/iam.tf` to a dedicated workload role. Configure the host's trust relationship separately; the repository cannot infer the correct trust principal until the deployment host is selected.

The runtime policy permits only:
- reads of bucket location, versioning, Object Lock, encryption, and public-access-block configuration;
- listing the ledger event prefix;
- reading objects and versions, inspecting object retention, and writing under `evidence/*`.

It does not grant object deletion, bucket creation, bucket-policy changes, or retention administration.

Run `python scripts/production_preflight.py` from a trusted checkout to verify Vault and S3 configuration without modifying resources or printing secret values. The bucket must have:
- versioning enabled;
- Object Lock enabled;
- default COMPLIANCE retention with an owner-reviewed duration;
- all four S3 Block Public Access settings enabled;
- default AES256 or AWS KMS server-side encryption.

The runtime identity needs `s3:GetObjectRetention` to read the object-retention metadata used by the verifier. If using AWS KMS instead of AES256, configure the corresponding narrowly scoped KMS permissions and update the deployment review before use.

Do not set `enable_bucket_creation=true` until the exact AWS account, bucket name, region, retention duration, cost, and legal hold requirements are approved. COMPLIANCE retention cannot be shortened for objects while they remain retained.

## 6. Functional and recovery testing

Use a dedicated non-production AWS account and isolated Object Lock bucket. Verify:
- valid permit event is appended and chain head advances;
- identical repeat event IDs and payloads return the original ledger hash;
- reusing an event ID with changed payload is rejected;
- incomplete reservations or missing receipts fail the verifier and require reconciliation;
- a concurrent head update fails closed;
- an unlinked immutable event is detected by `scripts/verify_chain.py`;
- an interrupted write can be reconciled before writes resume;
- owner signatures reject expiry, scope changes, altered content and invalid keys;
- Stripe signatures reject invalid requests;
- `payout.paid` events are recorded once and are not treated as proof of bank settlement;
- no path can initiate a charge, refund, transfer, payout, email, SMS or outreach action.

## 7. Deployment approval

Before production:
1. Select a dedicated container host and confirm cost and region.
2. Configure its workload identity, Vault AppRole and network access.
3. Pass CI on the exact reviewed commit.
4. Pass isolated S3 and webhook integration tests.
5. Complete rate limiting, monitoring, alerting, key rotation, backup/restore and incident-response drills.
6. Review the production change and approve a controlled deployment.

No production deployment or irreversible S3 retention is authorized by this runbook.
