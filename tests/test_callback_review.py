"""Internal fixtures only: no customer examples or external transmissions."""
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pytest

from fulfillment.callback_review import ReviewInputError, review_csv

AS_OF = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
COLUMNS = [
    "lead_id", "inquiry_at", "first_contact_at", "followup_due_at",
    "followup_completed_at", "estimate_sent_at", "estimate_response_at",
    "customer_reply_at", "next_action", "assigned_owner",
    "appointment_at", "appointment_confirmed_at",
]


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def output_rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_distinct_evidence_based_reasons_and_manifest(tmp_path):
    base = dict.fromkeys(COLUMNS, "")
    rows = [
        dict(base, lead_id="a", inquiry_at="2026-11-05T08:00:00Z", assigned_owner="Owner A"),
        dict(base, lead_id="b", inquiry_at="2026-11-05T08:00:00Z", first_contact_at="2026-11-05T10:00:00Z", followup_due_at="2026-11-07T10:00:00Z"),
        dict(base, lead_id="c", inquiry_at="2026-11-05T08:00:00Z", first_contact_at="2026-11-05T10:00:00Z", estimate_sent_at="2026-11-06T10:00:00Z"),
        dict(base, lead_id="d", inquiry_at="2026-11-05T08:00:00Z", first_contact_at="2026-11-05T10:00:00Z", customer_reply_at="2026-11-07T08:00:00Z"),
        dict(base, lead_id="e", inquiry_at="2026-11-05T08:00:00Z", first_contact_at="2026-11-05T10:00:00Z", next_action="Check Thursday"),
    ]
    inp, out = tmp_path / "buyer.csv", tmp_path / "review.csv"
    write_csv(inp, COLUMNS, rows)
    receipt = review_csv(inp, out, AS_OF)
    reviewed = {r["lead_id"]: r for r in output_rows(out)}
    assert len(reviewed) == 5
    assert "FIRST_CONTACT_NOT_RECORDED" in reviewed["a"]["reason_codes"]
    assert "OVERDUE_FOLLOWUP_RECORDED" in reviewed["b"]["reason_codes"]
    assert "ESTIMATE_RESPONSE_NOT_RECORDED" in reviewed["c"]["reason_codes"]
    assert "CUSTOMER_REPLY_NEXT_ACTION_MISSING" in reviewed["d"]["reason_codes"]
    assert reviewed["e"]["verification_status"] == "NOT_FLAGGED"
    assert reviewed["b"]["review_priority"] == "P1"
    assert reviewed["d"]["review_priority"] == "P1"
    assert reviewed["a"]["review_priority"] == "P2"
    assert output_rows(out)[0]["lead_id"] == "b"
    assert receipt["source_row_count"] == receipt["output_row_count"] == 5
    assert receipt["no_external_actions"] is True
    assert len(receipt["input_sha256"]) == len(receipt["output_sha256"]) == 64
    assert json.loads(Path(str(out) + ".manifest.json").read_text()) == receipt
    assert "Owner A" not in json.dumps(receipt)
    assert os.stat(out).st_mode & 0o077 == 0
    assert os.stat(Path(str(out) + ".manifest.json")).st_mode & 0o077 == 0


def test_missing_activity_columns_is_unverified_not_missed_call(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at"], [{"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00Z"}])
    review_csv(inp, out, AS_OF)
    row = output_rows(out)[0]
    assert row["verification_status"] == "UNVERIFIED"
    assert row["reason_codes"] == "ACTIVITY_COLUMNS_MISSING"
    assert "nobody" not in row["callback_reasons"].lower()


def test_blank_first_contact_column_is_record_gap_not_claim_of_no_call(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at", "first_contact_at"], [{"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00Z", "first_contact_at": ""}])
    review_csv(inp, out, AS_OF)
    row = output_rows(out)[0]
    assert row["verification_status"] == "RECORD_GAP"
    assert "actual contact is unverified" in row["callback_reasons"]


def test_malformed_time_is_not_classified_as_overdue(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at", "first_contact_at", "followup_due_at", "followup_completed_at"], [
        {"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00Z", "first_contact_at": "bad", "followup_due_at": "2026-11-02T12:00:00Z", "followup_completed_at": ""}
    ])
    review_csv(inp, out, AS_OF)
    row = output_rows(out)[0]
    assert row["verification_status"] == "UNVERIFIED"
    assert row["reason_codes"] == "INVALID_TIMESTAMP"


@pytest.mark.parametrize("row_count", [0, 51])
def test_empty_or_oversized_export_rejected(tmp_path, row_count):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at"], [{"lead_id": f"L{i}", "inquiry_at": "2026-11-01T12:00:00Z"} for i in range(row_count)])
    with pytest.raises(ReviewInputError):
        review_csv(inp, out, AS_OF)
    assert not out.exists()


def test_duplicate_id_rejected_without_output(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at"], [{"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00Z"}] * 2)
    with pytest.raises(ReviewInputError, match="unique"):
        review_csv(inp, out, AS_OF)
    assert not out.exists()


def test_existing_output_is_not_overwritten(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at"], [{"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00Z"}])
    out.write_text("do not overwrite")
    with pytest.raises(ReviewInputError, match="new files"):
        review_csv(inp, out, AS_OF)
    assert out.read_text() == "do not overwrite"


def test_timezone_required(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at"], [{"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00"}])
    review_csv(inp, out, AS_OF)
    assert output_rows(out)[0]["verification_status"] == "UNVERIFIED"


def test_future_inquiry_is_unverified(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at"], [{"lead_id": "A", "inquiry_at": "2027-11-01T12:00:00Z"}])
    review_csv(inp, out, AS_OF)
    assert output_rows(out)[0]["reason_codes"] == "INVALID_INQUIRY_TIME"


def test_owner_only_is_not_activity_evidence(tmp_path):
    inp, out = tmp_path / "in.csv", tmp_path / "out.csv"
    write_csv(inp, ["lead_id", "inquiry_at", "assigned_owner"], [{"lead_id": "A", "inquiry_at": "2026-11-01T12:00:00Z", "assigned_owner": "X"}])
    review_csv(inp, out, AS_OF)
    assert output_rows(out)[0]["reason_codes"] == "ACTIVITY_COLUMNS_MISSING"
