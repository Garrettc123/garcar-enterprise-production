# Repair: lead enrichment contract

## Symptom
Synthetic CRF jobs targeted `services/enrichment.py` which does not exist.
Real intake is `backend/leads.py` and only accepted email/name/source.

## Fix
`POST /api/leads/capture` now accepts optional:
- phone
- team_name
- market
- crm
- notes

Values are folded into `Lead.notes` (no DB migration).
Duplicate emails merge enrichment instead of dropping it.

## Offer alignment
Supports DFW RE $2,500 lead-backup intake fields without schema risk.

## Gate
Draft PR only. Human merge required. No `automerge` label.
