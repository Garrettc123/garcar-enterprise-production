# GARCAR Enterprise Platform

**AI-powered business automation for revenue operations.**
Deal Desk intelligence, SEO Content Factory, and Churn Prediction — delivered as production API services with multi-tier access controls, Stripe billing, and an automated email nurture pipeline.

**Live Frontend:** [garcar-enterprise-platform](https://www.perplexity.ai/computer/a/garcar-enterprise-platform-xp0pc.wORSmfOdADtNVa0g)

---

## Contents

- [Platform Overview](#platform-overview)
- [System Architecture & Visibility Boundary](#system-architecture--visibility-boundary)
- [API Products](#api-products)
- [Pricing Tiers](#pricing-tiers)
- [Deployment Architecture](#deployment-architecture)
- [Environment Variables](#environment-variables)
- [Email Nurture System](#email-nurture-system)
- [API Authentication](#api-authentication)
- [Local Development](#local-development)
- [Operational Roadmap](#operational-roadmap)

---

## Platform Overview

GARCAR Enterprise Platform is the public-facing API layer of the Unified Enterprise Execution Platform (UEEP). It exposes three production AI services—Deal Desk, SEO Content Factory, and Churn Predictor—to paying customers via JWT and API key authentication, Stripe subscription management, and a 5-step automated email nurture pipeline.

This repository contains the complete public runtime: FastAPI backend, SQLite persistence, Stripe webhook processing, SMTP drip sequencing, and deployment configuration for Railway and Render. The proprietary orchestration systems, agent execution engines, and internal operational infrastructure that power the broader UEEP are maintained in private repositories and secured environments.

**Current milestone:** Scaling recurring revenue to first stable MRR through direct B2B customer acquisition in contractor, agency, and SaaS verticals.

---

## System Architecture & Visibility Boundary

The UEEP is organized into a tiered visibility model that separates the public interface layer from the private execution core. This repository is the public boundary: it handles all external requests, enforces data contracts, manages billing and auth, and routes execution to private services.

<details>
<summary>View High-Level UEEP Architecture Diagram</summary>

```
┌─────────────────────────────────────────────────────────────┐
│                   PUBLIC INTERFACE LAYER                    │
│               (This repository — public)                    │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  TITAN API  │  │  Auth / JWT  │  │  Stripe Billing   │  │
│  │   Gateway   │  │  API Keys    │  │  Webhook Handler  │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘  │
│         └────────────────┴──────────────────┘              │
│                          │                                  │
│              Request Validation (Pydantic)                  │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │   PRIVATE ORCHESTRATION LAYER   │
          │        (closed-source)          │
          │                                 │
          │  ┌──────────────────────────┐   │
          │  │  Internal Orchestration  │   │
          │  │  & Execution Engines     │   │
          │  └──────────────────────────┘   │
          │  ┌──────────────────────────┐   │
          │  │  Agent State & Workflow  │   │
          │  │  Persistence Services    │   │
          │  └──────────────────────────┘   │
          │  ┌──────────────────────────┐   │
          │  │  Protected Business      │   │
          │  │  Logic & Decision Rules  │   │
          │  └──────────────────────────┘   │
          └─────────────────────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │   PROTECTED DATA & STATE LAYER  │
          │        (private infra)          │
          │                                 │
          │  Agent memory · Audit trails    │
          │  Secure data stores · Telemetry │
          └─────────────────────────────────┘
```

*Gray blocks: public interface layer in this repository. Colored blocks: private orchestration, execution services, and protected state infrastructure.*

</details>

### Public Interface Layer (This Repository)

| Component | Responsibility |
|-----------|---------------|
| TITAN API Gateway | Validates and routes all external API requests (Python 3.11+, FastAPI, Pydantic) |
| Auth Service | JWT token issuance and API key management |
| Stripe Billing | Subscription lifecycle, webhook processing, plan enforcement |
| Product Routers | Deal Desk, SEO Factory, and Churn Predictor endpoint logic |
| Email Nurture | SMTP-based 5-step drip sequence for new lead onboarding |

### Private Execution Layer (Closed-Source)

The following systems operate in secured private environments and are not included in this repository.

- **Internal orchestration engines** — proprietary multi-agent coordination and task routing
- **Execution logic** — sensitive automation, decision trees, and operational workflow processing
- **Agent state management** — persistent execution memory, workflow state, and audit records
- **Protected infrastructure** — private data stores, internal telemetry, and observability services

### Why this boundary exists

This separation allows technical reviewers to inspect public contracts, schemas, authentication flows, and service interfaces without exposing sensitive operational logic. Reviewers can trace exactly how a request enters the platform, how it is validated, how billing is enforced, and how it is handed off to private services — while proprietary execution remains isolated.

---

## API Products

| Product | Endpoint | Description |
|---------|----------|-------------|
| AI Deal Desk | `POST /api/products/deal-desk/analyze` | Score deals, get win probability and recommended strategy |
| SEO Content Factory | `POST /api/products/seo-factory/generate` | Generate optimized content briefs and full article drafts |
| Churn Predictor | `POST /api/products/churn-predictor/predict` | Predict customer churn risk with actionable recommendations |

---

## Pricing Tiers

| Plan | Price | API Calls/month |
|------|-------|----------------|
| Free | $0 | 10 |
| Starter | $49/mo | 500 |
| Professional | $149/mo | 5,000 |
| Enterprise | $499/mo | Unlimited |

---

## Deployment Architecture

This platform is deployed across two production-ready targets: Render and Railway. Both are auto-configured via included manifest files.

```
Frontend (Static SPA)     →  Backend (FastAPI + SQLite)  →  Stripe (Payments)
index.html / app.js           main.py + routers              Webhooks / SMTP
Deployed: Static Host         Deploy: Railway or Render       Email Nurture
```

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

> **Mobile-first DevOps note:** This platform is actively managed and deployed from a Termux-based environment using standard Git, Docker, and Railway/Render CLI tooling — demonstrating that full-stack cloud deployment does not require a traditional desktop pipeline.

---

## Environment Variables

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

---

## Email Nurture System

Every new lead is auto-enrolled in a 5-step welcome sequence.

| Step | Timing | Content |
|------|--------|---------|
| 1 | Immediate | Welcome + platform overview |
| 2 | Day 1 | Quick win — 30-second Deal Desk walkthrough |
| 3 | Day 3 | Churn cost awareness and risk framing |
| 4 | Day 5 | SEO competitive urgency |
| 5 | Day 7 | Upgrade pitch with plan comparison |

### Processing the Queue

```bash
# Manual trigger (admin auth required)
POST /api/nurture/process

# Recommended: scheduled cron job hitting the process endpoint every hour
# Or use the "Process Queue" button in the Nurture dashboard tab
```

---

## API Authentication

```bash
# Register
curl -X POST https://your-api.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@co.com", "password": "pass", "name": "You"}'

# Authenticate with Bearer token
curl -H "Authorization: Bearer YOUR_TOKEN" ...

# Or authenticate with API key
curl -H "X-API-Key: gce_your_key" ...
```

---

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py  # starts on :8000

# Frontend
cd frontend
npx serve -p 3000
```

---

## Operational Roadmap

| Phase | Target | Status |
|-------|--------|--------|
| Phase 1 | Production API deployment with Stripe billing | ✅ Live |
| Phase 2 | B2B customer acquisition — contractor and agency verticals | 🔄 Active |
| Phase 3 | First stable recurring MRR milestone | 🎯 Target |
| Phase 4 | Multi-tenant expansion and additional product verticals | 📋 Planned |
| Phase 5 | Full UEEP private orchestration layer integration | 📋 Planned |

---

## Intellectual Property & Defensive Publications

The broader UEEP architecture, including the RHNS coordination protocols and Zero-Human governance patterns, is documented through public prior-art records archived on Zenodo and in public GitHub repositories. These publications establish architectural priority and protect the concepts underlying the private execution layer while keeping implementation details proprietary.

- [Garrettc123 / zero-human-governance-core](https://github.com/Garrettc123/zero-human-governance-core) — public governance contracts and interface specifications
- Zenodo archives: architectural design documentation for UEEP, RHNS, and related systems

---

Built by [Garrett Carroll](https://github.com/Garrettc123) · GARCAR Enterprise · Fort Worth, TX
