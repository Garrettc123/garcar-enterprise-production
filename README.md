# GARCAR Enterprise Platform

AI-powered business automation — Deal Desk, SEO Content Factory, and Churn Predictor.

**Live Frontend:** [GARCAR Enterprise Platform](https://www.perplexity.ai/computer/a/garcar-enterprise-platform-xp0pc.wORSmfOdADtNVa0g)

## Architecture

```
Frontend (Static SPA)     →  Backend (FastAPI + SQLite)  →  Stripe (Payments)
index.html / app.js           main.py + routers              Webhooks
Deployed: Perplexity          Deploy: Railway/Render          SMTP (Email)
```

## Products

| Product | Endpoint | Description |
|---------|----------|-------------|
| AI Deal Desk | `POST /api/products/deal-desk/analyze` | Score deals, get win probability and strategy |
| SEO Content Factory | `POST /api/products/seo-factory/generate` | Generate optimized content briefs and articles |
| Churn Predictor | `POST /api/products/churn-predictor/predict` | Predict customer churn risk with recommendations |

## Pricing

| Plan | Price | API Calls/mo |
|------|-------|-------------|
| Free | $0 | 10 |
| Starter | $49/mo | 500 |
| Professional | $149/mo | 5,000 |
| Enterprise | $499/mo | Unlimited |

## Backend Deployment (Railway or Render)

### Option A: Render

1. Create account at [render.com](https://render.com)
2. Connect GitHub repo `garcar-enterprise-production`
3. Render auto-detects `render.yaml` — click Deploy
4. Set environment variables (see below)

### Option B: Railway

1. Create account at [railway.app](https://railway.app)
2. Connect GitHub repo
3. Railway auto-detects `railway.toml`
4. Set environment variables

### Environment Variables

```env
# Required
JWT_SECRET=<generate-a-strong-random-string>
DATABASE_URL=sqlite:///./garcar.db

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email Nurture (for drip sequences)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
FROM_NAME=GARCAR Enterprise
FROM_EMAIL=hello@garcar.io

# Frontend URL (for CORS + emails)
ALLOWED_ORIGINS=https://your-frontend-url.com
BASE_URL=https://your-frontend-url.com
```

## Email Nurture System

5-step welcome drip sequence auto-enrolls every new lead:

1. **Immediate:** Welcome + product overview
2. **Day 1:** Quick win — 30-second Deal Desk challenge
3. **Day 3:** Churn cost awareness
4. **Day 5:** SEO competitive urgency
5. **Day 7:** Upgrade pitch with plan comparison

### Processing the Queue

The nurture queue must be processed periodically. Options:

1. **Manual:** `POST /api/nurture/process` (admin auth required)
2. **Cron job:** Add a scheduled task that hits the process endpoint every hour
3. **In-app:** Click "Process Queue" in the Nurture dashboard tab

## API Authentication

```bash
# Register
curl -X POST https://your-api.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@co.com", "password": "pass", "name": "You"}'

# Use Bearer token
curl -H "Authorization: Bearer YOUR_TOKEN" ...

# Or use API key
curl -H "X-API-Key: gce_your_key" ...
```

## Local Development

```bash
cd backend
pip install -r requirements.txt
python main.py  # starts on :8000

# Frontend: serve static files on any port
cd frontend
npx serve -p 3000
```

---

Built by [Garrett Carroll](https://github.com/Garrettc123) — GARCAR Enterprise, Fort Worth TX
