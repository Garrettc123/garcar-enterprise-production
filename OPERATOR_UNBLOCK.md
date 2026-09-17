# Operator unblock — 3 tasks

## 1. Supabase
Paste and run from `garcar-revenue-os`:
`supabase/migrations/APPLY_ALL.sql`

## 2. Edge webhook
```bash
cd workers/stripe-webhook
npx wrangler deploy
npx wrangler secret put STRIPE_WEBHOOK_SECRET
```
Or fix Vercel billing: https://vercel.com/teams/garcar-enterprise/settings/billing

## 3. Stripe + HubSpot
- Stripe → Webhooks → endpoint = Worker URL
- Events: checkout.session.completed, payment_intent.succeeded
- HubSpot: reply **Approve HubSpot contact** in chat to create operator contact
