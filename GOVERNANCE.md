# Evidence, approval, and payment boundaries

- Evidence enrichment uses a provider contract. The default provider returns no records; ratings and project counts remain unknown.
- Owner approval statements are HMAC-SHA256 signed and scoped to one permit, a short validity window, named evidence references, and a small allowlist of non-financial actions.
- Approval validation does not execute the approved action. No email, outreach, export, charge, refund, transfer, or payout is initiated.
- Stripe webhook events must pass Stripe's signature verification. Only a small allowlist of event metadata is retained for reconciliation. The complete Stripe payload is not stored.
- Stripe event recording is not payout authorization and does not move funds.
- Configure `OWNER_APPROVAL_SIGNING_KEY` and `STRIPE_WEBHOOK_SECRET` only in Vault KV; never place them in source control or chat.
