# Evidence, approval, and payment boundaries

## Evidence enrichment
- Evidence enrichment uses a provider contract. The default provider returns no records; ratings and project counts remain unknown.
- RHNS policy is deterministic and fail-closed. It requires verified permit source, contractor identity, authority, evidence references, a budget ceiling, and an owner approval.
- The current intake path supplies none of those attestations automatically, so new permits remain in HUMAN_REVIEW_REQUIRED.
- Numeric risk scores are not fabricated.

## Owner approval
- Owner approval statements are Ed25519 signed and scoped to one permit, a validity window, evidence references, and a small allowlist of draft/export actions.
- The API stores only the Ed25519 public key. The private signing key remains offline with the owner.
- Generate a keypair locally with `scripts/generate_owner_keypair.py`; store only the printed public key in Vault as `OWNER_APPROVAL_PUBLIC_KEY`.
- Sign a structured approval JSON locally with `scripts/sign_owner_approval.py`; submit the approval JSON and returned signature in `X-Garcar-Approval-Signature`.
- Approval validation does not execute the approved action. No email, outreach, export, charge, refund, transfer, or payout is initiated by this service.

## Immutable chain
- Permit, approval, and Stripe reconciliation events share one ordered S3 hash chain.
- Each event includes a sequence number and previous-event hash; the head is advanced with an S3 conditional write.
- If concurrent writers race, the losing immutable event is left unlinked and the request fails closed. The chain verifier reports the inconsistency; manual reconciliation is required before writes resume.
- Use `scripts/verify_chain.py` to verify the complete sequence, hashes, head pointer, and retention metadata.

## Stripe
- Stripe webhook events must pass Stripe's signature verification.
- Only a small allowlist of event metadata is retained for reconciliation. The full Stripe payload is not stored.
- Stripe event recording is not payout authorization and does not move funds.
- Store `STRIPE_WEBHOOK_SECRET` only in Vault.

## Production boundary
- Terraform bucket creation remains disabled by default.
- No production deploy, cloud resource creation, external outreach, or financial action is part of this implementation.
