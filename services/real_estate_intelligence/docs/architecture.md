# REOS v0.2 architecture and next integration steps

## Request paths

```
Official registry links ----> human data review ----> /v1/cases (SQLite)
RHNS agent (agent key) ----> /v1/agent-proposals ----> HUMAN approver ----> case
case ----> evidence + underwriting ----> HUMAN research approval
case ----> diligence checklist ----> HUMAN offer review ----> external contract record
case ----> tasks + unsent drafts (NO automated outreach)
case ----> read-only dossier JSON for downstream RHNS/Private OS consumers
Stripe --> signature verification --> REOS-tagged live PI receipt table (NO charge creation)
                                      |
                         hash-chained local audit events
```

## Trust boundaries

Operator key: list/create research, tasks, calculate estimates and save drafts. This key can see all case data; protect it as sensitive. Approver key: distinct, added only for decisions and high-risk transitions. Agent key: distinct, used to **submit** candidate research but cannot approve. Stripe webhook: Stripe-Signature HMAC with anti-replay window; no API-key authentication required for this one endpoint. HTTPS, IP allowlist and upstream rate limiting are deployment responsibilities.

## Data persistence

- `cases`: unique normalized address key, raw validated property snapshot, research review status.
- `evidence`: individual dated source assertions.
- `underwriting`: assumptions and deterministic screened results.
- `buyers`: buyer **criteria** only, no personal contacts.
- `decisions`: separate research approval/rejection decisions.
- `case_phases`: current tracked transaction workflow position.
- `checklist`: last operator review for each of ten diligence topics.
- `tasks`: case deadlines and status.
- `agent_proposals`: pending/accepted/rejected candidate property research.
- `drafts`: unsent messages only.
- `verified_stripe_receipts`: validated live REOS-tagged successful Stripe PaymentIntent receipts.
- `audit`: hash-chained event headers. Payload hashes do not include full immutable payload snapshots, and an admin can rewrite history.

SQLite is appropriate only for one private staging service. For public SaaS, design Postgres migration + per-tenant role isolation, backups, structured audit anchoring, secrets rotation, replay-safe idempotency and retention before enabling users. No implicit multi-tenant access is allowed.

## Cross-platform integration sequence

1. RHNS read-only worker: `GET /v1/cases/{id}/dossier` with operator-service key scoped to a private gateway (future fine-grained service roles); submit new proposals with isolated `REOS_AGENT_KEY`.
2. Private control plane: publish only case id, phase, evidence freshness and approval status as a signed event into existing governance adapter. A decision outcome in REOS is not a governance override.
3. Garcar revenue OS: reuse existing approval gates; do not send outreach from REOS or create duplicate payment processing.
4. Stripe: existing approved billing platform tags successful PaymentIntents and forwards Stripe-signed webhook to REOS, if and when configured. No duplicate charge flow.
5. County/MLS data: secure permitted license/API access first; source links today are human research pointers, NOT scraped live feeds.
6. Attorney/title provider: off-platform documents and verified deed records; no pretend automated contract signature.
