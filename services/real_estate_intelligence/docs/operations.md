# REOS operational controls and integration sequence

## Control boundaries
1. **Read-only intake:** ingest buyer-owned/legally accessible property records and explicit source links. No automated county scraping; verify public-record terms and request limits before adding a connector.
2. **Review underwriting:** manual ARV support from true comparable sales, itemized repair estimates, title/ownership research, and recorded assumptions.
3. **Approval:** operator reviews source records, marks evidence reviewed, then a distinct approver credential permits **research approval only**. Never interpret this as seller authorization, signature, title clearance, or brokerage compliance.
4. **Buyer matches:** research leads only; no claim that a company has funding or committed to a purchase.
5. **Transaction gate:** attorney/title officer verifies contracts, equitable interest disclosures, license issues, applicable consumer rules and closing documents outside REOS. No offer submission or assignment in the module.
6. **Communication gate:** outbound integrations not implemented. Any future automation requires explicit per-recipient approval, lawful basis for contact, opt-out handling, DNC/TCPA/CAN-SPAM checks as applicable, and an auditable action receipt.
7. **Privacy:** no owner phone/email/SSN/bank details stored; restrict repository access and database backups. Segregate tenant data before multi-tenant launch.

## Existing Garcar components
- `garcar-enterprise-production` remains system of record and source tree; REOS is separate service with no new master control plane.
- `garcar-private-control-os` or RHNS could consume **read-only** REOS case summaries behind authentication in a separate approved integration. No silent integration or agent write permissions are included.
- `garcar-revenue-os` sales approval gate remains authoritative for any customer outreach; REOS deliberately has no send functions.
- Stripe billing and payment webhooks are out of scope until the existing verified live payment path passes independent checks.

## Texas requirements
Texas Occupations Code §1101.0045 and 22 TAC §535.6 require disclosure in writing of the nature of an equitable interest to potential buyers and sellers when selling/assigning that interest. Trading in a contract right is not a general exemption to conduct brokerage. Verify current laws and documents with qualified Texas counsel before transactions.

Sources: https://www.trec.texas.gov/agency-information/rules-and-laws/trec-rules
https://statutes.capitol.texas.gov/GetStatute.aspx?Code=OC&Value=1101.0045

## Limitations requiring further engineering
- Does not verify county record ownership or property title against primary sources; source URLs are operator-declared.
- Review marks are operator assertions; 90-day freshness is a configurable business policy only in the next version.
- No observed market data, deployed dashboard, MLS licensing, contact enrichment, payment or CRM sync.
- SHA chain is internal and rewriteable by DB administrators; external anchoring/backup verification not yet provided.
- SQLite single-service deployment only; for scale use Postgres with row-level authorization, per-tenant isolation, encrypted backups and signed approvals.
- No rate limiting, request-size enforcement, external OIDC, or production TLS termination: deploy only behind a secure gateway with these controls.

## Release gates
1. Verify all CI tests on exact pinned commit.
2. Deploy to staging, configure strong independent secrets + TLS reverse proxy, no public write endpoints.
3. Run real legally sourced property dataset with explicit source attribution and reproducible underwriting.
4. Verify backup/restore, audit integrity, logging and access controls.
5. Approve buyer outreach/transaction process separately with legal review.
