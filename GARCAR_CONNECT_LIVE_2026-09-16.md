# Garcar Connect — Non-Simulation Live Run
**Date:** 2026-09-16 15:51 CDT
**Mode:** REAL MCP secrets (no simulation)

## Live Stripe (acct_1SS3dpFKGbk21LK5)
- Canonical webhook: https://garcar-payments.garrettc123.workers.dev/stripe-webhook
- Hot leads in Stripe customers:
  - Michael Gibson — New View Roofing (Hot, $2500 + $997/mo)
  - Will Miller — Priority Roofing (Hot, highest probability)
  - Ben Posey — AM Roofing (Warm, $47 Diagnostic)
  - Jon Stewart / Ken Donaghy — re-engage $47 Diagnostic

## Local Canary (already passed)
- 11 leads ingested
- 30 outreach jobs scheduled (email + LinkedIn)
- Stripe idempotency verified ($47 event)

## Next
1. Owner-level dial / Gmail to Hot list
2. Confirm canonical webhook receives checkout.session.completed
3. Promote full Connect path to production host
