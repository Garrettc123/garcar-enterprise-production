# Garcar Lead Capture Worker

Cloudflare Worker for the Garcar Enterprise RevOps lead pipeline.

## Endpoints

- `GET /health` — health/configuration status
- `POST /leads` — validate, score, and persist a lead

## Required Cloudflare secrets

Set these with Wrangler. Do not commit values to GitHub:

```bash
wrangler secret put SUPABASE_URL
wrangler secret put SUPABASE_ANON_KEY
wrangler secret put HF_SCORER_URL
```

## Deploy

From the repository root:

```bash
wrangler deploy
```

The included `wrangler.toml` names the Worker `garcar-lead-capture` and points to `workers/lead-capture.js`.

## Supabase table

The Worker expects a `leads` table that accepts the following fields:

- `name`
- `email`
- `phone`
- `company`
- `website`
- `message`
- `source`
- `metadata`
- `lead_score`
- `lead_label`
- `scoring_result`

Use a Supabase migration to create or alter the table before production deployment. The Worker intentionally does not attempt schema creation at runtime.

## Test

```bash
curl https://<your-worker-domain>/health

curl -X POST https://<your-worker-domain>/leads \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"Test Lead",
    "email":"test@example.com",
    "company":"Example Co",
    "source":"website",
    "message":"Interested in an AI revenue automation demo"
  }'
```

The worker uses Cloudflare environment bindings (`env.*`) and never embeds secrets in source control.
