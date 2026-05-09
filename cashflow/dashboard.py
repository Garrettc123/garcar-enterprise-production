"""GAR-423: Real-time cashflow dashboard
Vercel-deployable FastAPI. Pulls from Stripe + Redis cache.
Frontend: /finance route, mobile-responsive.
"""
import os
import json
import stripe
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta

try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = FastAPI(title="Garcar Cashflow Dashboard")
CACHE_TTL = 60  # seconds


def get_stripe_metrics() -> dict:
    cache_key = "garcar:cashflow:metrics"
    if REDIS_AVAILABLE:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)

    now = datetime.utcnow()
    month_start = int(datetime(now.year, now.month, 1).timestamp())

    # MRR from subscriptions
    try:
        subs = stripe.Subscription.list(status="active", limit=100)
        mrr = sum(
            (s.items.data[0].price.unit_amount or 0) / 100
            for s in subs.auto_paging_iter()
            if s.items.data
        )
    except Exception:
        mrr = 0

    # Monthly charges
    try:
        charges = stripe.Charge.list(created={"gte": month_start}, limit=100)
        total_collected = sum(c.amount / 100 for c in charges.auto_paging_iter() if c.paid)
        pending = sum(c.amount / 100 for c in charges.auto_paging_iter() if not c.paid)
    except Exception:
        total_collected = 0
        pending = 0

    metrics = {
        "mrr": round(mrr, 2),
        "total_collected_month": round(total_collected, 2),
        "pending": round(pending, 2),
        "allocation": {
            "owner_pay_40pct": round(total_collected * 0.40, 2),
            "operations_25pct": round(total_collected * 0.25, 2),
            "tax_reserve_20pct": round(total_collected * 0.20, 2),
            "reinvestment_15pct": round(total_collected * 0.15, 2),
        },
        "refreshed_at": now.isoformat(),
    }

    if REDIS_AVAILABLE:
        r.setex(cache_key, CACHE_TTL, json.dumps(metrics))

    return metrics


@app.get("/finance", response_class=HTMLResponse)
async def dashboard():
    m = get_stripe_metrics()
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Garcar Cashflow Dashboard</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #f0f0f0; margin: 0; padding: 20px; }}
    h1 {{ color: #00d4aa; font-size: 1.4rem; margin-bottom: 1rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
    .card {{ background: #1a1a1a; border: 1px solid #333; border-radius: 10px; padding: 16px; }}
    .card .label {{ font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card .value {{ font-size: 1.6rem; font-weight: 700; color: #00d4aa; margin-top: 4px; }}
    .alloc {{ margin-top: 20px; }}
    .alloc-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #222; font-size: 0.9rem; }}
    .refresh {{ font-size: 0.7rem; color: #555; margin-top: 12px; }}
    meta[http-equiv] {{ }}
  </style>
  <meta http-equiv="refresh" content="60">
</head>
<body>
  <h1>Garcar Enterprise — Cashflow</h1>
  <div class="grid">
    <div class="card"><div class="label">MRR</div><div class="value">${m['mrr']:,.2f}</div></div>
    <div class="card"><div class="label">Collected (MTD)</div><div class="value">${m['total_collected_month']:,.2f}</div></div>
    <div class="card"><div class="label">Pending</div><div class="value">${m['pending']:,.2f}</div></div>
  </div>
  <div class="alloc">
    <h2 style="font-size:1rem; color:#888; margin:16px 0 8px;">Allocation Breakdown</h2>
    <div class="alloc-row"><span>Owner Pay (40%)</span><span style="color:#00d4aa">${m['allocation']['owner_pay_40pct']:,.2f}</span></div>
    <div class="alloc-row"><span>Operations (25%)</span><span>${m['allocation']['operations_25pct']:,.2f}</span></div>
    <div class="alloc-row"><span>Tax Reserve (20%)</span><span>${m['allocation']['tax_reserve_20pct']:,.2f}</span></div>
    <div class="alloc-row"><span>Reinvestment (15%)</span><span>${m['allocation']['reinvestment_15pct']:,.2f}</span></div>
  </div>
  <div class="refresh">Auto-refreshes every 60s — Last updated: {m['refreshed_at']}</div>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/finance/api")
async def finance_api():
    return get_stripe_metrics()


@app.get("/health")
def health():
    return {"status": "ok", "service": "cashflow-dashboard"}
