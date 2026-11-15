# Garcar Follow-Up Review — Buyer-Facing Scope
**Provider:** Garcar Enterprise LLC
**Offer:** One-time lead follow-up review, `MLS-497`
**Price:** $497 USD, one-time; no recurring subscription for the review.
**Verified active Stripe link (2026-11-09):** https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h
**Stripe description:** "Mark the leads that sat" (the checkout text and service title should be made consistent before widespread promotion).

## Customer outcome
Turn **one authorized customer-owned lead export** into an actionable list showing which leads warrant a callback, the evidence-based reason, the suggested owner, and what information needs confirmation. Findings describe the supplied records, not unseen actions in the customer's business.

## Inputs
- Customer supplies **one recent export**, initially up to 50 rows, from an existing CRM or spreadsheet; no CRM migration or vendor change.
- Minimum useful fields: customer lead identifier, inquiry date/time, last-contact date/time or documented activity history, current status, and existing assignment if available.
- Optional inputs: estimate/quote status, appointment status, lead source, last customer response, promised follow-up date.
- Anonymized IDs are acceptable for preliminary validation. Avoid sending raw lead lists by ordinary email; agree a secure transfer and authorized use first.
- The customer retains responsibility for lawful access, contact consent, and accuracy of provided records.

## Decision rules and traceable reasons
Every recommended action must cite the exact supporting fields in the exported record.
- **No recorded first contact:** Inquiry exists and no first-contact event is present. Say "no contact recorded," not "nobody called."
- **Overdue committed follow-up:** A supplied follow-up due date has passed and no later completion is recorded.
- **Estimate/quote awaiting reply:** A quote was sent and the supplied activity history shows no later response or follow-up.
- **Customer replied, next step missing:** A reply is present but no documented owner/next action exists.
- **Appointment or callback needs confirmation:** The data shows an outstanding commitment without recorded completion.
- **Insufficient evidence:** Missing timestamps/status/history. Output `UNVERIFIED` and a question to resolve; never invent a callback failure.

Prioritization may use the customer-approved business rules (e.g. age, value, urgency), but not ungrounded claims about job value, lost revenue, or customer intent. Different rows need not have different reasons unless the records justify them.

## Deliverables
1. Reviewed CSV or workbook, preserving the customer's identifiers and source field references.
2. Callback/action queue with `reason`, `supporting_fields`, `verification_status`, `suggested_next_action`, `assigned_owner_if_provided`, and `priority_basis`.
3. One-page summary of supported findings, blocked or ambiguous records, and recommended process changes.
4. Short acceptance walkthrough, plus corrections of factual transcription/classification errors identified within the agreed scope.

**Target turnaround:** Within 48 hours after both payment confirmation and a usable, securely transferred export. If input quality or access blocks completion, notify the buyer and agree an adjusted timeline.

## Explicit exclusions
- No automatic email, SMS, dialing, or contact with the buyer's leads.
- No guarantee of revenue increase, response rates, conversions, or recovered sales.
- No full CRM installation, ongoing monitoring, broad historical data cleaning, or customized integrations in the $497 review.
- No synthetic leads, fabricated before/after results, or unsupported claims of customer activity.
- A separate **$2,500 Callback Clock installation** can be quoted later, subject to approved specifications and integration validation.

## Delivery / acceptance record
Record the verified Stripe payment ID, buyer consent to process the export, data receipt timestamp, export hash, review output checksum, limitations, delivery confirmation, and any requested corrections. Do **not** treat an open checkout, unpaid invoice, failed charge, or draft as a paid engagement.

## Operator quality gate
Before sending the output:
- All listed lead IDs originate from buyer-supplied records.
- No category claims an unrecorded event happened.
- Every suggested callback reason is supported or labeled UNVERIFIED.
- Row counts and totals reconcile to the source file.
- Personal data is minimized, access-restricted, and retained only per agreed handling terms.
- Customer outreach or access to their CRM requires its own explicit authorization.

This specification is a scope artifact, not evidence that a paid customer or production deployment exists.
