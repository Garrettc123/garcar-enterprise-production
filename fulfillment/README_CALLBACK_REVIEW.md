# Follow-Up Review — Operator Runbook

**Status:** Review-branch implementation. No customer production delivery has been verified.
**Offering:** One $497 Lead Follow-Up Review using buyer-owned, explicitly authorized records.
**Scope:** Up to 50 rows from one CSV; no outbound action, customer contact, or CRM write.

## Privacy and source authorization

Obtain authorization to process the specific export under the agreed service terms. Agree on a secure file-transfer location before accepting contact details. Keep customer files outside the Git repository, with restricted filesystem permissions and a retention/deletion agreement. Do not upload buyer-owned lead records, payment details, or contact lists to GitHub issues, CI artifacts, sales demos, or ordinary email.

## CSV input contract

Required columns:
- `lead_id`: real, unique identifier from the customer-owned source; never create missing IDs.
- `inquiry_at`: ISO-8601 timestamp with timezone, e.g. `2026-11-09T13:41:00-06:00`.

Optional columns (exact headers):
- `first_contact_at`
- `last_contact_at`
- `followup_due_at`
- `followup_completed_at`
- `estimate_sent_at`
- `estimate_response_at`
- `customer_reply_at`
- `next_action`
- `assigned_owner`
- `appointment_at`
- `appointment_confirmed_at`

Every populated `*_at` field must use an ISO-8601 timezone offset. A blank field is treated as **not recorded in the supplied export**; it does not prove an action never occurred. If relevant activity columns are absent, the row is marked `UNVERIFIED`, not a missed follow-up.

Headers are case-sensitive. Map a customer's actual export to these headers only after identifying the appropriate corresponding source fields; preserve the original export and document the mapping separately. Do not infer contact events that cannot be substantiated.

## Offline execution

From the repository root, after storing an authorized buyer export in a restricted local directory:

```bash
python -m fulfillment.callback_review --input "$AUTHORIZED_LEAD_EXPORT" --output "$REVIEW_OUTPUT_CSV" --as-of "2026-11-09T13:41:00-06:00"
```

The operator sets both paths explicitly. The output file must not exist already; it is never overwritten. The processor creates:
- A restricted-permission CSV at the chosen output path, preserving real lead IDs and evidence-linked reasons.
- A JSON manifest at the output path plus `.manifest.json`, containing row counts, statuses, SHA-256 hashes, and review as-of timestamp, without contact PII.

No external HTTP calls, email, SMS, CRM updates, or payments are performed.

## Review rules

- `FIRST_CONTACT_NOT_RECORDED`: supplied `first_contact_at` column exists but has no entry.
- `OVERDUE_FOLLOWUP_RECORDED`: follow-up due time passed and supplied completion column has no entry.
- `ESTIMATE_RESPONSE_NOT_RECORDED`: estimate sent, no subsequent estimate response recorded.
- `CUSTOMER_REPLY_NEXT_ACTION_MISSING`: reply recorded, next-action field blank.
- `APPOINTMENT_CONFIRMATION_NOT_RECORDED`: appointment exists, confirmation field blank.
- `INVALID_TIMESTAMP` / `INVALID_INQUIRY_TIME` / `ACTIVITY_COLUMNS_MISSING`: inputs cannot support a finding.
- `NO_RULE_TRIGGERED`: no finding from available fields, not proof all work was completed.

The processor never creates a lead, invents an estimated deal value, asserts a person was never called, or infers recovered revenue.

## Verification and fulfillment

Run `python -m pytest -q tests/test_callback_review.py` and preserve the test report; internal fixtures are allowed for unit testing and must not appear as buyer data.

Before delivery: reconcile each source identifier, verify input and output row counts, inspect every flagged reason against its source fields, review the manifest hashes, and correct any unsupported action classifications. This initial processor lists evidence-based findings but does **not** calculate an independently validated rank ordering or handle buyer-specific rules automatically. Human review and an agreed priority policy remain required.

The manifest is a **local checksum record**, not independently immutable evidence. Independent integrity requires storing/verifying its digest in a separately protected system.

Record separately (outside GitHub): the confirmed Stripe payment identifier, customer authorization, dataset receipt time, review as-of time, delivery confirmation, privacy/retention terms, and requested corrections. Never infer a completed sale from an active payment link.

## Hold / stop conditions

- Missing buyer authorization or required fields.
- 0 or more than 50 rows.
- Duplicate/blank lead IDs.
- Invalid activity timestamps making a row unverifiable.
- Output file exists or secure storage cannot be ensured.
- Any attempt to automatically contact buyer leads or modify customer systems.

Do not deploy or advertise this as production-validated until repository CI passes and one permitted customer dataset has been processed and independently reviewed.
