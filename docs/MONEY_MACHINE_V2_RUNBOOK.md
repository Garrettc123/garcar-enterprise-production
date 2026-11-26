# Garcar Money Machine v2 — Evidence-First Revenue Operations

Status: Implementation proposal, with callback-review capacity and verification tools in this branch. Do not interpret this document as a live deployed sales agent, a payment settlement, or proof of production client delivery.

## Objective and commercial scope

Build one repeatable, governed loop for DFW real-estate teams already buying leads:

Discover -> qualify -> draft -> founder approval -> contact -> paid $497 Lead Follow-Up Review -> authorized export -> guarded review -> human QA -> delivery -> optional $2,500 Callback Clock installation -> referral.

The $497 review is credited toward the separately quoted $2,500 installation only when the agreed contract states so. The 48-hour turnaround is a target from receipt of approved usable data, not a guarantee. No guaranteed incremental sales or claimed revenue recovery.

Do not expand verticals until real conversion and fulfilled customer outcomes justify it.

## Capability boundaries

| Capability | State in this pull request | Next proof required |
| --- | --- | --- |
| Offline 500-record CSV classification | Code expanded from 50 to 500; 2 MB input cap retained | Dedicated CI passes; authorized customer acceptance |
| Evidence-linked priority reasons | Existing deterministic logic, no guessed contacts | Validate real client source mappings and human QA |
| PII-safe output manifest | Existing SHA-256 manifest | Local verifier passes and independently anchored digest if contract requires |
| Tamper detection | New local input/output hash, schema, count and status verifier | Run on generated artifacts before customer delivery |
| Dedicated review CI | New workflow and regression tests | GitHub Actions result for branch and post-merge main |
| Autonomous prospect research | Planned; not implemented in this PR | Real source provenance and deduped account candidates |
| Autonomous outbound | Intentionally locked | Founder approves exact recipient, copy and send action |
| Stripe purchase confirmation | Not verified by this PR | Reconcile authoritative successful live charge in correct account |
| Automated customer delivery | Intentionally locked | Buyer authorization, file handling terms, human review |

## Revenue state machine

1. DISCOVERED: public organization record and provenance recorded; no guessed contacts.
2. QUALIFIED: real-estate team, existing inbound lead activity, decision-maker role, DFW geography, ICP fit evidence.
3. DRAFT_READY: proposed message and reason for fit; no sending.
4. APPROVED_TO_CONTACT: exact person, channel, copy, compliance footer, and expiration approved by founder.
5. CONTACTED: delivery evidence from the actual provider; do not infer sent from draft.
6. REPLIED: human reply linked to original message, recorded without inferred intent.
7. REVIEW_ORDERED: buyer scope, privacy terms, payment instructions, and authorized source requested.
8. PAID_VERIFIED: successful live Stripe charge reconciled in the correct account with customer and product; no revenue from draft links or pending intents.
9. DATA_AUTHORIZED: express permission and approved secure-transfer channel for the particular buyer-owned export.
10. REVIEW_COMPLETED: deterministic local CSV report and checksum manifest generated without external actions.
11. VERIFIED_AND_QA: integrity verification and human field-by-field review passed; unsupported claims removed.
12. DELIVERED: actual buyer receipt and completion timestamp recorded.
13. INSTALL_PROPOSED / INSTALL_CONTRACTED: optional scoped $2,500 project, separately accepted and paid before changes.
14. REFERRAL_REQUESTED: only after authorized delivery; no preapproved blanket messaging.

Any ambiguous evidence, deliverability issue, payment-account mismatch, missing consent, timestamp error, or unsupported claim transitions to HOLD_FOR_HUMAN rather than auto-completing.

## Agent responsibility design (future iteration, not yet deployed)

- Research Agent: identify real ICP-matched teams; store link, observed date, and source.
- Qualification Agent: use only verifiable attributes, explain each qualify/reject decision.
- Message Agent: draft one personalized and accurate commercial message; no synthetic testimonials.
- Governance Agent: enforce exact-message send approval, CAN-SPAM and suppression rules.
- Payment Reconciler: read exact Stripe livemode transaction status; prevent duplicate order events.
- Fulfillment Agent: run the offline deterministic callback review only on approved files.
- Quality Agent: call the verifier, reconcile output counts, and queue human sign-off.
- Expansion Agent: suggest install rules derived from this customer's confirmed gaps, never fabricated ROI.
- Scorecard Agent: compile six weekly metrics plus cash collected with source IDs and timestamps.

These are named responsibilities for a single orchestrator, not a request to deploy nine separate autonomous services.

## Required safety and reliability controls

- Idempotency: unique keys by (source_system, external_event_id, event_type); reject reprocessing after a success receipt.
- Data minimization: store operational evidence and references, not buyer lead CSVs, in the CRM and GitHub.
- Approval: no outbound email, social DMs, charges, refunds, CRM writes, or buyer-delivery actions without the necessary explicit approval.
- Financial truth: book revenue only from confirmed completed external livemode payments; distinguish test/sandbox and legacy accounts.
- Per-customer isolation: secure local input and output paths, 0600 file modes, retention/deletion terms, never include buyer PII in GitHub/CI.
- Audit: preserve SHA-256 artifacts and source event IDs; local manifest is not immutable proof, and a compromised party can replace both data and manifest.
- Failsafe: stop workflow on unknown schema, duplicate IDs, invalid offsets, unapproved input, verifier failure, or capacity exceedance.
- Budget: no paid enrichment, advertising, compute provisioning, or bulk outbound without an approved ceiling.
- Claims: tests and fixture rows must never be reported as customer results or sales proof.

## Production review commands

From the repository root, after approved secure receipt of a real buyer export:

    python -m fulfillment.callback_review --input "$AUTHORIZED_LEAD_EXPORT" --output "$REVIEW_OUTPUT_CSV" --as-of "$AGREED_AS_OF_WITH_OFFSET"

    python -m fulfillment.verify_review --input "$AUTHORIZED_LEAD_EXPORT" --output "$REVIEW_OUTPUT_CSV" --manifest "$REVIEW_OUTPUT_CSV.manifest.json"

A successful verifier means only that the provided bytes and local manifest are consistent. It does not attest to buyer consent, CRM accuracy, independently anchored evidence, or payment.

## Weekly scorecard

Record: new teams contacted, human replies, meetings booked, $497 reviews sold, $2,500 installs sold, hours from accepted data to delivered report, and actual external cash collected.

Each KPI row must have source system, time window, exact event IDs, verification state, and deduplication key. Unavailable is not zero. No performance claim from incomplete data.

## Release gates

- G1: callback-review CI green on the exact commit and main after merge.
- G2: approved customer-owned export at agreed scope; accepted schema and secure transfer verified.
- G3: checksum verifier pass, analyst spot-check, and independent buyer approval of deliverable.
- G4: verified live paid order tied to correct Stripe account before marking "sold."
- G5: send and deliver separately approved and evidenced.
- G6: explicit rollback and customer correction procedure documented before deploying an install.

Until all applicable gates pass, label the system as engineering-ready or guarded pre-revenue, not proven autonomous revenue.
