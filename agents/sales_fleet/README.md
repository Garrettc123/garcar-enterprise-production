# Autonomous Sales Fleet

Run the read-only planning path with `python -m agents.sales_fleet.fleet --sku 497 --limit 10`. The GitHub workflow supports manual dispatch. The $2,500 installation is scope-first.

Supply operator records through `FLEET_LEAD_JSON` or use optional Apollo People Search. Without either source the fleet reports zero leads. Apollo search provides research records. Draft eligibility requires a company, usable email, verified email status, source ID or source URL, a documented consent basis (requested contact, existing customer or opt-in), and the configured fit threshold. Explicitly suppressed and test-tagged rows are excluded. Missing optional title, location and industry stay empty.

Live email requires an explicit live run, a healthy payment endpoint, a configured sender and a recipient-bound GAR-530 approval. A provider acceptance ID is recorded on successful submission. It does not establish inbox delivery or a sale.
