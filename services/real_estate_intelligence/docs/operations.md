# REOS v0.2 operations and launch controls

## Control model

- Single-operator private service; protect `X-API-Key` independently from `X-Approver-Key` and `X-Agent-Key`.
- Agents submit research proposals, but cannot accept/approve them without the separate human approver key. Never distribute that credential to agents.
- The UI is a private case manager, not a licensed listing service or a public real estate portal. Research URLs are **not** direct authorized data feeds.
- All draft communications remain unsent. No HTTP endpoint transmits email, SMS, calls, contracts, real estate offers or fund movements.
- A tracking label of `under_contract` or `closed` records **operator assertion** supported by a URL, not a verified executed legal instrument. Confirm externally with title/legal professionals.
- A completed diligence checklist indicates operator-reviewed source links; REOS cannot certify ownership, liens, ARV, zoning, repairs, title or legal clearance.
- Buyer matches are preliminary criteria checks, not proof of funds, exclusivity or contact consent.
- Signed live Stripe events count a narrow subset of gross payment events only. It is **not** a Stripe reconciliation system for refunds, chargebacks, fees, payouts or taxes.
- No source includes a scraped dataset, direct MLS access, or automatically discovered real properties.

## Before staging

1. Pin a passing commit and verify CI, dependency vulnerability review and code review.
2. Mount durable storage at `/data`; set `REOS_DB_PATH=/data/reos.sqlite`; one application replica only. SQLite does not support transparent multi-region scaling.
3. Configure **three independent 32-byte-or-longer** high-entropy keys using a secret manager; never commit keys or put them in API responses.
4. Configure HTTPS, allowlisted operator ingress / identity-aware proxy, rate limits and request limits. The dashboard has no login UI: it uses typed API keys in memory. This is not ready for general-public access.
5. If activating Stripe, configure a dedicated endpoint and `whsec_...`, require live Stripe account event signature validation and verify product metadata; don't enable new charges.
6. Test backup/restore (and audit validity on both). Hash-chain check alone cannot prove database administrators did not rewrite history.
7. Review TREC, title, property data licensing, Do Not Call/TCPA, and appropriate commercial email rules before any contact or transaction.

## Ongoing daily workflow

1. Visit official portals, record source URL and observed time; check license/terms for automation before importing anything.
2. Add research case or have RHNS submit agent proposal; separate reviewer may accept into the casebook.
3. Underwrite from explicit estimates and maintain source evidence for asking, ARV, repairs, and ownership; never treat tax appraisal as ARV.
4. Research approver reviews four current fields (90 days) and manually approves research only.
5. Finish all ten diligence checklist items with source/reviewer. Escalate title and legal questions externally; do not automatically pass them.
6. Move case through `qualified`, `diligence`, `offer_review` only with required gates. Record any external contract/closing URL purely as an operator assertion.
7. Track deadlines in tasks; draft communications as unsent, requiring a separate outbound authorization and execution mechanism if implemented in the future.
8. Use `/v1/audit/verify`; back up SQLite file with a consistent SQLite snapshot, encrypt at rest and store off service. Verify restore periodically.
9. Use `/v1/revenue/summary` only to report signed gross receipts for the tagged product; consult Stripe directly for refunds/fees/net and bank for settlement.

## Research starting points

- Johnson CAD: https://johnsoncad.com/property-search/ (tax appraisal not ARV).
- Johnson County Clerk: https://www.johnsoncountytx.org/government/county-clerk/online-records (online database may be incomplete versus official records).
- TREC rules: https://www.trec.texas.gov/agency-information/rules-and-laws/trec-rules
- Texas Occupations Code: https://statutes.capitol.texas.gov/Docs/OC/html/OC.1101.htm

## Texas legal boundary

Texas Occupations Code § 1101.0045 and TREC Rule § 535.6 address disclosure and equitable-interest assignments. Obtain current qualified Texas real estate counsel review. Never advertise property ownership or represent others without applicable authority; REOS does not provide legal advice.

## Limitations and future hardening

- Single-operator local SQLite (no row-level tenant separation, OIDC/RBAC, API rate limits, customer auth, backup automation or disaster recovery proof).
- Database hash trail is internal, not externally anchored; integrity is not independently attested.
- API docs disabled, but the dashboard is publicly retrievable as static HTML and requires a private API key for data. Keep private behind an identity-aware gateway rather than exposing it broadly.
- External systems (RHNS, Stripe, CRM, title company, MLS, e-sign) are **interface-compatible, not necessarily actively integrated or authenticated**.
- Not SOC 2 certified, HIPAA-validated, MLS-licensed, or ready for public multi-tenant use.
