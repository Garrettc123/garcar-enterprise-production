"""Offline, evidence-bounded review of one customer-owned lead CSV.

Does not call remote services, contact leads, calculate speculative lost revenue,
or infer that a person was never contacted from an absence of records.
Python standard library only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path

RULES_VERSION = "callback-review-v1"
MAX_ROWS = 50
REQUIRED_COLUMNS = frozenset({"lead_id", "inquiry_at"})
OPTIONAL_COLUMNS = frozenset({
    "first_contact_at", "last_contact_at", "followup_due_at",
    "followup_completed_at", "estimate_sent_at", "estimate_response_at",
    "customer_reply_at", "next_action", "assigned_owner", "appointment_at",
    "appointment_confirmed_at",
})
TIMESTAMP_COLUMNS = frozenset({"inquiry_at"}) | frozenset(
    c for c in OPTIONAL_COLUMNS if c.endswith("_at")
)
OUTPUT_COLUMNS = [
    "lead_id", "assigned_owner", "verification_status", "reason_codes",
    "callback_reasons", "source_fields", "suggested_next_action",
    "priority_basis", "source_row_sha256",
]


class ReviewInputError(ValueError):
    """A buyer export cannot be safely classified without correction."""


def parse_aware(value: str, field: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewInputError(f"Invalid ISO-8601 timestamp in {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewInputError(f"Timestamp {field} must include UTC offset")
    return parsed.astimezone(timezone.utc)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def review_row(row: dict[str, str], columns: set[str], as_of: datetime) -> dict[str, str]:
    clean = {str(k): str(v or "").strip() for k, v in row.items() if k is not None}
    lead_id = clean["lead_id"]
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    evidence = []
    invalid = []
    timestamps = {}
    for field in sorted(TIMESTAMP_COLUMNS & columns):
        try:
            timestamps[field] = parse_aware(clean.get(field, ""), field)
        except ReviewInputError:
            invalid.append(field)
    if invalid:
        return {
            "lead_id": lead_id,
            "assigned_owner": clean.get("assigned_owner", ""),
            "verification_status": "UNVERIFIED",
            "reason_codes": "INVALID_TIMESTAMP",
            "callback_reasons": "Cannot classify reliably: timestamp missing offset or invalid in " + ", ".join(invalid),
            "source_fields": ";".join(invalid),
            "suggested_next_action": "Correct timestamp format with the source owner before prioritization",
            "priority_basis": "None: input requires correction",
            "source_row_sha256": sha256(canonical),
        }
    inquiry = timestamps.get("inquiry_at")
    if inquiry is None or inquiry > as_of:
        return {
            "lead_id": lead_id,
            "assigned_owner": clean.get("assigned_owner", ""),
            "verification_status": "UNVERIFIED",
            "reason_codes": "INVALID_INQUIRY_TIME",
            "callback_reasons": "Inquiry timestamp absent or after review as-of time",
            "source_fields": "inquiry_at",
            "suggested_next_action": "Confirm inquiry timestamp before review",
            "priority_basis": "None: inquiry time unverified",
            "source_row_sha256": sha256(canonical),
        }
    if "followup_due_at" in columns and timestamps.get("followup_due_at"):
        due = timestamps["followup_due_at"]
        if due < as_of and "followup_completed_at" in columns and not timestamps.get("followup_completed_at"):
            evidence.append(("OVERDUE_FOLLOWUP_RECORDED", "Follow-up due date has passed with no completion recorded in this export", "followup_due_at,followup_completed_at", "Verify status with owner; schedule callback only if authorized", due.isoformat()))
    if "customer_reply_at" in columns and timestamps.get("customer_reply_at") and "next_action" in columns and not clean.get("next_action"):
        evidence.append(("CUSTOMER_REPLY_NEXT_ACTION_MISSING", "Customer reply recorded but next action field is blank", "customer_reply_at,next_action", "Assign a documented next step after owner review", timestamps["customer_reply_at"].isoformat()))
    if "estimate_sent_at" in columns and timestamps.get("estimate_sent_at") and "estimate_response_at" in columns and not timestamps.get("estimate_response_at"):
        evidence.append(("ESTIMATE_RESPONSE_NOT_RECORDED", "Estimate sent; no subsequent estimate response recorded in this export", "estimate_sent_at,estimate_response_at", "Confirm quote status and plan appropriate follow-up", timestamps["estimate_sent_at"].isoformat()))
    if "appointment_at" in columns and timestamps.get("appointment_at") and "appointment_confirmed_at" in columns and not timestamps.get("appointment_confirmed_at"):
        evidence.append(("APPOINTMENT_CONFIRMATION_NOT_RECORDED", "Appointment exists without a confirmation recorded in this export", "appointment_at,appointment_confirmed_at", "Check appointment confirmation with the responsible person", timestamps["appointment_at"].isoformat()))
    if "first_contact_at" in columns and not timestamps.get("first_contact_at"):
        evidence.append(("FIRST_CONTACT_NOT_RECORDED", "No first contact recorded in supplied export; actual contact is unverified", "inquiry_at,first_contact_at", "Verify activity history; contact the lead only if permitted", inquiry.isoformat()))

    if evidence:
        return {
            "lead_id": lead_id,
            "assigned_owner": clean.get("assigned_owner", ""),
            "verification_status": "RECORD_GAP",
            "reason_codes": "|".join(e[0] for e in evidence),
            "callback_reasons": " | ".join(e[1] for e in evidence),
            "source_fields": "|".join(e[2] for e in evidence),
            "suggested_next_action": " | ".join(e[3] for e in evidence),
            "priority_basis": "|".join(e[4] for e in evidence),
            "source_row_sha256": sha256(canonical),
        }
    if not ((OPTIONAL_COLUMNS - {"assigned_owner", "next_action"}) & columns):
        status = "UNVERIFIED"
        reason_code = "ACTIVITY_COLUMNS_MISSING"
        reason = "Export lacks follow-up and contact activity columns; no callback assessment possible"
        next_action = "Request an authorized activity-history export or confirm records with the owner"
    else:
        status = "NOT_FLAGGED"
        reason_code = "NO_RULE_TRIGGERED"
        reason = "No review rule triggered in supplied fields; this does not establish complete follow-up"
        next_action = "No action recommended from available fields; review if more activity history is available"
    return {
        "lead_id": lead_id,
        "assigned_owner": clean.get("assigned_owner", ""),
        "verification_status": status,
        "reason_codes": reason_code,
        "callback_reasons": reason,
        "source_fields": "inquiry_at" if status == "UNVERIFIED" else ";".join(sorted(OPTIONAL_COLUMNS & columns)),
        "suggested_next_action": next_action,
        "priority_basis": "No inferred urgency",
        "source_row_sha256": sha256(canonical),
    }


def review_csv(input_csv: Path, output_csv: Path, as_of: datetime) -> dict:
    """Write a restricted-permission review and a PII-free verification manifest.

    Outputs must not already exist; source and output cannot be the same file.
    """
    input_csv, output_csv = Path(input_csv), Path(output_csv)
    manifest_path = Path(str(output_csv) + ".manifest.json")
    if input_csv.resolve() == output_csv.resolve() or output_csv.exists() or manifest_path.exists():
        raise ReviewInputError("Output and manifest must be new files, distinct from source")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ReviewInputError("Review as-of time must include a timezone offset")
    as_of = as_of.astimezone(timezone.utc)
    data = input_csv.read_bytes()
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or any(not x for x in columns):
            raise ReviewInputError("Input has duplicate or blank header names")
        missing = sorted(REQUIRED_COLUMNS - set(columns))
        if missing:
            raise ReviewInputError("Missing required CSV columns: " + ", ".join(missing))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ReviewInputError("Input must be valid UTF-8 CSV") from exc
    if not rows or len(rows) > MAX_ROWS:
        raise ReviewInputError(f"Expected 1 to {MAX_ROWS} buyer-owned lead rows")
    seen = set()
    results = []
    for row in rows:
        if None in row:
            raise ReviewInputError("CSV has rows with more fields than header")
        lead_id = str(row.get("lead_id") or "").strip()
        if not lead_id or lead_id in seen:
            raise ReviewInputError("Lead IDs must be present and unique")
        seen.add(lead_id)
        results.append(review_row(row, set(columns), as_of))

    output_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(output_buffer, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(results)
    output_bytes = output_buffer.getvalue().encode("utf-8")
    manifest = {
        "rules_version": RULES_VERSION,
        "as_of_utc": as_of.isoformat(),
        "input_sha256": sha256(data),
        "output_sha256": sha256(output_bytes),
        "source_row_count": len(rows),
        "output_row_count": len(results),
        "status_counts": dict(Counter(r["verification_status"] for r in results)),
        "no_external_actions": True,
        "interpretation": "Record gaps are not proof a person was never contacted or revenue was lost",
    }
    fd = os.open(output_csv, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(output_bytes)
        fd_m = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd_m, "w", encoding="utf-8") as out:
            json.dump(manifest, out, indent=2, sort_keys=True)
            out.write("\n")
    except BaseException:
        output_csv.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline evidence-bounded review of a buyer-authorized lead CSV")
    parser.add_argument("--input", required=True, type=Path, help="Buyer-owned UTF-8 CSV")
    parser.add_argument("--output", required=True, type=Path, help="New CSV path (will not overwrite)")
    parser.add_argument("--as-of", required=True, help="ISO-8601 date/time with timezone offset")
    args = parser.parse_args()
    as_of = parse_aware(args.as_of, "--as-of")
    if as_of is None:
        raise ReviewInputError("--as-of is required")
    manifest = review_csv(args.input, args.output, as_of)
    print(json.dumps({"status": "review_complete", "row_count": manifest["output_row_count"], "manifest": str(args.output) + ".manifest.json"}))


if __name__ == "__main__":
    main()
