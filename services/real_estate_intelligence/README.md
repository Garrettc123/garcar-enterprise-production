# Garcar Real Estate Intelligence OS (REOS) — v0.2

**A working private research-and-operations service. Not a licensed brokerage, automated wholesaler, title service, appraisal or deployed customer platform.**

Garcar REOS lives within `Garrettc123/garcar-enterprise-production/services/real_estate_intelligence`. It does **not** replace the Garcar Private OS governance plane, automate prohibited outbound outreach or assume live investor revenue.

## Delivered workflow (end-to-end as case tracking, not unattended transaction execution)

`Official research links → evidence-first property intake / RHNS proposal queue → human agent-proposal review → underwriting → evidence-based research approval → qualification → 10-item due diligence checklist → human offer review → external contract tracking → external closing tracking → signed payment event reconciliation → audit.`

- **Dashboard** at `/dashboard`: connected portfolio counters, casebook, property registration, source evidence, underwriting, diligence checklist, workflow transitions, task queue, agent proposals, source registry.
- **API**: private FastAPI with an API credential, separate human approver key, separate agent key, security headers, no CORS wildcard, and disabled documentation unless explicitly enabled.
- **Property intake**: individually or from a validated local CSV, source URL, timestamp, duplicate-address protection; no speculative listing scraper.
- **Investment screening**: deterministic, explicit ARV, repair, holding, closing, financing, reserves, target profit, assignment fee and selling costs; independent 70% heuristic upper bound.
- **RHNS integration surface**: typed research proposals with dedicated agent credential; **only a human approver** can accept a proposal to create a case; agents cannot approve a case or make offers.
- **Workflow tracker**: `intake → research → qualified → diligence → offer_review → under_contract → closed`, plus disqualification. High-risk transitions require a separate approver key and external agreement/closing references; no actual signatures or notices are sent.
- **Research gates**: fresh operator-reviewed evidence in 4 categories; fresh 10-item diligence checklist for offer review. Operator checks are assertions, not independent market or title certifications.
- **Task workflow**: due queue, case-scoped tasks, priority, completion and blocked status; **no automated messages**.
- **Buyer criteria matching**: manual registered organization-level criteria only, no personal contacts, purchase commitments, or cash claims.
- **Communication drafting**: unsent, local-only drafts with no recipient address and no send endpoint.
- **Revenue receipts**: optional Stripe `payment_intent.succeeded` signed webhook (live, REOS-tagged only). Records gross successful payment events, never claims bank settlement/profit or absence of refunds. No checkout creation or charge authorization.
- **Audit**: transactional SQLite state, hash-chain integrity check. Hashes are internally tamper-evident, **not immutable or externally anchored**.

## Local launch

Python 3.11+ required. From the `services/real_estate_intelligence` directory:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
export REOS_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export REOS_APPROVER_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export REOS_AGENT_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export REOS_DB_PATH="$(pwd)/data/reos.sqlite"
uvicorn garcar_reos.api:app --host 127.0.0.1 --port 8091
```

Open `http://127.0.0.1:8091/dashboard`. Click **Connect API key**, provide the operator key and optionally the separate approver key. Both exist only in the active browser tab memory; reload clears them. This is a *single-operator* dashboard, not a multi-tenant SaaS product.

A Dockerfile is available. External deployment **requires** TLS, a private gateway or trusted identity provider, a persistent volume, independently stored credentials, request-rate limits, backups and restore verification. Do not point an unauthenticated public domain at sensitive operator data. Use `/health` for readiness checks.

## Core API

Every `/v1/*` call requires `X-API-Key`. **Never expose keys in URLs or screenshots.**

| Route | Purpose |
| --- | --- |
| `GET /health` | Public, no private data |
| `GET /dashboard` | Static operator UI; API fetches require auth |
| `GET /v1/sources` | Official research portals and limitations |
| `GET/POST /v1/cases` | List and register property cases |
| `GET /v1/cases/{id}/dossier` | Consolidated case packet for approved RHNS read-only workflows |
| `POST /v1/cases/{id}/evidence` | Store source-backed evidence |
| `POST /v1/cases/{id}/underwrite` | Deterministic screening |
| `POST /v1/cases/{id}/research-decision` | Requires `X-Approver-Key` |
| `GET/POST /v1/cases/{id}/phase` | State transitions; high-risk transitions require approval |
| `GET/PUT /v1/cases/{id}/checklist` | Ten-item diligence evidence gates |
| `POST/GET /v1/cases/{id}/tasks` | Operator task assignments |
| `PATCH /v1/tasks/{task_id}` | Operator changes task status |
| `GET /v1/tasks/due` | Pending due work (manual polling) |
| `GET/POST /v1/cases/{id}/drafts` | Unsent notes/drafts only |
| `POST /v1/agent-proposals` | Also requires `X-Agent-Key`; never executes proposals |
| `GET /v1/agent-proposals` | Human review queue |
| `POST /v1/agent-proposals/{id}/decision` | Also requires `X-Approver-Key` |
| `POST /v1/buyers`, `GET /v1/cases/{id}/buyer-matches` | Criteria-based, noncommittal matching |
| `GET /v1/portfolio` | Pipeline counters without fabricated revenue |
| `GET /v1/revenue/summary` | Authenticated signed live receipt summary, no settlements |
| `POST /integrations/stripe/webhook` | Stripe signature replaces API auth; REOS-tagged **live** PI events only |
| `GET /v1/audit/verify` | Verify hash sequence for all recorded actions |

## RHNS agent proposal format

`POST /v1/agent-proposals`, headers `X-API-Key`, `X-Agent-Key`:

```json
{
  "agent_id": "rhns-research-worker",
  "property": {
    "street_address": "ADDRESS_OBSERVED_IN_A_PERMITTED_SOURCE",
    "city": "Cleburne", "state": "TX", "postal_code": "76033",
    "county": "Johnson", "property_type": "single_family",
    "asking_price": "0.00", "source_url": "https://johnsoncad.com/property-search/",
    "observed_at": "2026-11-26T18:00:00-06:00"
  },
  "research_rationale": "Explain provenance, independent corroboration still needed."
}
```

This JSON is a **schema illustration, not a genuine property listing or lead**. Replace every placeholder with independently observed, licensed or permitted facts. A proposal stays `pending` until a separate human decision. No automated agent connection has been enabled at the RHNS end.

## Optional Stripe inbound receipt verification

Set `REOS_STRIPE_WEBHOOK_SECRET` using your Stripe endpoint's signing secret. Register the route in your verified Stripe account; explicitly configure `payment_intent.succeeded` delivery and attach metadata `reos_product=real_estate_intelligence` to REOS-specific PaymentIntents at creation time in the **approved existing billing platform**. REOS **does not create PaymentIntents or checkout links**. It validates Stripe-Signature (HMAC SHA-256 + 5-minute tolerance), checks `livemode=true`, and deduplicates both Stripe event and PaymentIntent IDs. No funds or financial outcomes exist until real signed events arrive. Refunds, disputes, settlement, fees and tax reporting are out of scope; do not equate gross events with earnings.

## Local CSV ingestion

```bash
reos --db ./data/reos.sqlite import-csv /path/to/permitted_properties.csv
reos --db ./data/reos.sqlite portfolio
reos --db ./data/reos.sqlite due-tasks
reos --db ./data/reos.sqlite verify-audit
```

CSV headers: `street_address,city,state,postal_code,county,property_type,asking_price,source_url,observed_at,operator_notes` (operator_notes optional). Only supply legally acquired data; do not include seller PII or bulk scraped personal contacts.

## Deployment readiness and limitations

See [operations runbook](docs/operations.md) and [system architecture](docs/architecture.md). This is runnable engineering functionality, **not** evidence of actual properties acquired, buyers committed, contracts signed, funds collected or SOC 2 compliance.
