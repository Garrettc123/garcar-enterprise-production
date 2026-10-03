# Approvals store (GAR-530)

Nothing in this folder except this README is ever committed (see `.gitignore`).

| File | Env var | Written by | Contents |
|---|---|---|---|
| `approvals.jsonl` | `APPROVALS_PATH` | **Garrett only**, via the CLI | Signed grant and revoke records |
| `approvals.used.jsonl` | `APPROVALS_USED_PATH` | the gate | One line per consumed use (append-only) |
| `policy_events.jsonl` | `APPROVAL_EVENTS_PATH` (or `EVENTS_PATH`) | the gate | `policy.action.allowed.v1` / `policy.action.refused.v1` events, MARS envelope v1.1 |

Keys (set in your vault / host env, **never** in git, CI logs, or PR text):

- `APPROVAL_SIGNING_KEY`: used by the CLI on Garrett's machine to sign records.
- `APPROVAL_VERIFY_KEY`: used by services to verify records. With HMAC-SHA256 this is the
  same value as the signing key, so anything holding it could mint approvals. Hardening
  follow-up: Ed25519 (services get only the public key).

Both must be at least 32 characters. Generate one locally with
`python -c "import secrets; print(secrets.token_urlsafe(48))"` and store it straight in
your vault.

## Issuing approvals

```bash
# one email to one recipient, valid 24h, one use
python -m approval_gate.cli grant --action send.email --to buyer@example.com --expires 24h --uses 1

# a sales-fleet batch: explicit recipients, one use each, short expiry
python -m approval_gate.cli grant --action send.email --to a@x.com --to b@y.com --uses 2 --expires 2h --print-record

# one invoice (PaymentIntent) up to $500 for one customer
python -m approval_gate.cli grant --action charge.payment_intent --to buyer@example.com --max-amount-cents 50000 --currency usd

# one revenue allocation (Stripe transfers) up to $2,000 total
python -m approval_gate.cli grant --action money.transfer --max-amount-cents 200000 --currency usd

# STANDING approval: self-serve checkout for one plan keeps the Pay button working
python -m approval_gate.cli grant --action charge.checkout --standing --plan starter --max-amount-cents 4900 --currency usd --expires 90d

python -m approval_gate.cli list
python -m approval_gate.cli revoke --id pd_...
```

Standing approvals exist **only** for `charge.checkout` (buyer-initiated). Invoices,
transfers, every send, and every call need a per-action ID with a use limit.

## What the gate refuses (fail closed)

Missing / unknown / revoked ID, bad signature, wrong action, expired, used up, recipient
not in scope, amount over cap or missing, wrong currency or plan, store unreadable,
verify key missing, audit log unwritable. No env var turns it off.
