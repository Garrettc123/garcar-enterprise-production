# Garcar Real Estate Intelligence OS (REOS) — v0.1

**Status: research software, not a deployed acquisition business.** This is a distinct module under
`Garrettc123/garcar-enterprise-production/services/real_estate_intelligence`.

## Delivered, runnable capabilities

- Evidence-first property intake with source URL, observed timestamp, deduplication and strict fields.
- Deterministic, configurable underwriting: cost-based seller acquisition cap and 70%-of-ARV heuristic cap;
  captures assumptions and generates estimated buyer economics and headroom.
- Source-evidence casebook, 90-day operator-reviewed evidence gate, explicit research decisions with separate approver credential.
- Buyer-criteria matching by county, property type, and maximum acquisition amount.
- Tamper-evident append-only-style SHA-256 audit chain; verification endpoint/command.
- SQLite persistence, authenticated FastAPI, offline CSV intake, scoped CI tests, Dockerfile.
- **No scraping, automatic emails/calls, offers, contracts, financial transfers, or trades.**

## Install / run locally (Python 3.11+)

```bash
cd services/real_estate_intelligence
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
export REOS_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export REOS_APPROVER_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export REOS_DB_PATH="$(pwd)/data/reos.sqlite"
uvicorn garcar_reos.api:app --host 127.0.0.1 --port 8091
```

For isolated standalone ZIP use, run the commands from its unpacked root instead.
`GET /health` is public and returns no property data. Every other endpoint requires `X-API-Key`.
`POST /v1/cases/{id}/research-decision` additionally requires `X-Approver-Key`.
Never use demo/example secrets in production. Use a managed secret store and TLS/authenticated reverse proxy
for any remote deployment. Do not expose a Docker port publicly without a reverse proxy; Dockerfile binds to localhost.

## Authenticated endpoints

| Method | Route | Function |
|---|---|---|
| GET | `/health` | Minimal health check |
| POST, GET | `/v1/cases` | Property intake, list |
| GET | `/v1/cases/{id}` | Case dossier |
| POST, GET | `/v1/cases/{id}/evidence` | Provenance documents |
| POST | `/v1/cases/{id}/underwrite` | Calculate grounded investment limits |
| GET | `/v1/cases/{id}/underwriting/latest` | Last saved calculation |
| GET | `/v1/cases/{id}/readiness` | Gate evidence and calculation |
| POST | `/v1/cases/{id}/research-decision` | Human-credential research approval/rejection |
| POST | `/v1/buyers` | Buyer investment criteria (no direct contacts) |
| GET | `/v1/cases/{id}/buyer-matches` | Preliminary buyer fits only |
| GET | `/v1/audit/verify` | Verify audit sequence |

## Offline CSV import (no synthetic leads)

```bash
reos --db ./data/reos.sqlite import-csv /path/to/your_verified_properties.csv
reos --db ./data/reos.sqlite list-cases
reos --db ./data/reos.sqlite verify-audit
```

Expected UTF-8 CSV header:

```csv
street_address,city,state,postal_code,county,property_type,asking_price,source_url,observed_at,operator_notes
```

The file may have fewer columns only if `operator_notes` is omitted. Valid `property_type`: `single_family`,
`multi_family`, `land`, `commercial`; timestamps must include time-zone offset. Only import data you are
permitted to use; do not add owner names, phone numbers, protected demographic attributes, or private data.
No fictitious market values or sample leads are supplied.

## Underwriting contract

`POST /v1/cases/{id}/underwrite` requires the following JSON fields:
`arv`, `repairs`, `closing_costs`, `holding_costs`, `financing_costs`, `reserve`,
`buyer_target_profit`, `proposed_assignment_fee`, and `selling_cost_rate`.
Optionally set `heuristic_arv_fraction` (defaults to `0.70`). Money inputs are decimal strings in USD.

`formula_mao = ARV × (1 − selling_cost_rate) − repairs − closing − holding − financing − reserve − buyer_target_profit − assignment_fee`.
`heuristic_mao = ARV × heuristic_arv_fraction − repairs`.
`maximum_allowable_offer = max(0, min(max(0, formula_mao), max(0, heuristic_mao)))`.

Both are **screening heuristics, not appraisals or guaranteed returns**. Buyer acquisition and seller consent
cannot be inferred from a match. Assumptions must come from dated, reviewed evidence before research approval.
Read [docs/operations.md](docs/operations.md) before making any investment decisions.
