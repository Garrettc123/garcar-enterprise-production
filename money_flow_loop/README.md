# Real Money Flow Loop — Garcar Enterprise

**Closed-loop revenue organism**

```
Attention → Trust Micro-Proof → Zero-Friction Trial → Instant Value
→ Paid Conversion → Expansion → Referral/Advocacy → New Attention
```

Every stage is designed to produce either real cash or a high-probability cash event.

## Architecture

| Module | Responsibility |
|--------|----------------|
| `orchestrator.py` | Central controller — ingests attention, advances stages, closes the loop |
| `stages/attention.py` | Capture + score new prospects; seed from advocacy |
| `stages/trust.py` | Live proof wall + one-click AI demo |
| `stages/trial.py` | Zero-friction 14-day full access + forced 48h win |
| `stages/conversion.py` | Stripe checkout integration (ties into existing `backend/payments.py`) |
| `stages/expansion.py` | Health scoring + outcome-based upsells |
| `stages/referral.py` | Advocacy program + auto case-study generation |
| `api.py` | FastAPI router — mount under `/api/money-flow` |

## Quick Start

1. Mount the router in `backend/main.py`:

```python
from money_flow_loop.api import router as money_flow_router
app.include_router(money_flow_router)
```

2. Ingest attention:

```bash
curl -X POST /api/money-flow/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "linkedin_founder", "email": "prospect@example.com"}'
```

3. Advance a prospect:

```bash
curl -X POST /api/money-flow/advance \
  -H "Content-Type: application/json" \
  -d '{"prospect_id": "...", "target_stage": "trial"}'
```

4. After a customer succeeds, close the loop:

```bash
curl -X POST /api/money-flow/close-loop \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "...", "outcome": {"roi": 3.8, "permission": true}}'
```

## Integration Points

- **Stripe**: Conversion stage reuses the exact plan definitions and checkout logic already in `backend/payments.py`.
- **Provisioning**: Trial stage is designed to call the existing `provision-customer` workflow.
- **Nurture**: Trust + Trial stages can hand off to `backend/nurture.py` sequences.
- **Churn / Expansion**: Expansion stage feeds the existing churn predictor and revenue allocator.

## Philosophy

This is not a funnel.
It is a living revenue organism.
Successful customers become the primary acquisition channel.
Cash moves at every conversion point.
The loop tightens with every closed cycle.

Built for the Zero-Human Platform.
