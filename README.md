# Garcar Enterprise — Live Offer

**Status: OPEN — public offer matches the landing page**

Effective: 2026-09-08  
Primary revenue surface: https://garrettc123.github.io/

## What is for sale right now

The page a stranger sees is the offer. Do not quote retired SKUs as if they were on that page.

| Offer | Price | How it is sold |
|-------|-------|----------------|
| Revenue System install | $2,000 | https://buy.stripe.com/7sYaEX1Ax1lU5YL3hx43S2e |
| Maintain | $1,000 / month | Checkout issued after install |

Retired (not on the live landing as of 2026-09-08): $47 audit, $497/wk sprint, $1,497/mo engine. Those Payment Links may still exist in Stripe. They are not the public pitch.

## Canonical payment webhook

- Checkout events: `https://garcar-payments.garrettc123.workers.dev/stripe-webhook`
- Grok connector only: subscription created/deleted
- Duplicate and 503 destinations were disabled 2026-09-08

## Operating rule

1. If someone pays the live $2,000 link, log it the same hour and start fulfillment. Do not open the $47 audit template unless they actually bought that retired SKU.
2. Do not charge any live link with card 4242 as if it were a customer.
3. Dated `*_CASH_LOCK_*.md` files are history.
4. MARS control-plane work stays draft until a human merges it.

## Founder

Garrett Carrol · garrett@garcar.io · Grandview / Kopperl, TX
