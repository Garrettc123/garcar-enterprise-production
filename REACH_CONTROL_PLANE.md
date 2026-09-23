# REACH control plane

Purpose: get Garcar in front of Johnson County / South DFW buyers every day without silent sends.

## Surfaces
| Channel | Asset |
|---|---|
| Store hub | https://garrettc123.github.io/store.html |
| Numbered products | /1 … /5 and garrettc1…garrettc5 repos |
| Trades closer | https://garrettc123.github.io/dfw-trades.html |
| RE closer | https://garrettc123.github.io/ |
| CRM | HubSpot portal 247022078 |
| Agents | ATLAS crew (dry-run default) |

## Daily loop
1. Open `reach/queue.csv` or regenerate via `python reach/generate_pack.py`.
2. Send from **your phone** — scripts already personalized.
3. Mark Sent / VM / Reply in the CSV or HubSpot task.
4. Paid Stripe → fulfill map inside 48h from ATLAS template.

## Hard gates
- HUMAN_SEND_REQUIRED on every outbound.
- No 4242 test charges.
- No VC lists from this plane.
- Stop means stop.

## System abilities (real)
- Multi-SKU public catalog + numbered short links
- ATLAS multi-agent map generation (dry-run or live LLM)
- HubSpot company/contact/deal sync
- Gmail operator drafts
- Five-city seed pack + Grandview published shop list
- SEO sitemap for discovery
