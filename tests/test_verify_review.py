"""Internal-only integrity tests; never buyer records or claimed customer results."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from fulfillment.callback_review import review_csv
from fulfillment.verify_review import ReviewVerificationError, verify_review


def _artifacts(tmp_path):
    source, report = tmp_path / "source.csv", tmp_path / "report.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["lead_id", "inquiry_at"])
        writer.writeheader()
        writer.writerow({"lead_id": "internal-only", "inquiry_at": "2026-11-01T12:00:00Z"})
    review_csv(source, report, datetime(2026, 11, 9, tzinfo=timezone.utc))
    return source, report, Path(str(report) + ".manifest.json")


def test_valid_local_manifest_can_be_verified(tmp_path):
    source, report, manifest = _artifacts(tmp_path)
    result = verify_review(source, report, manifest)
    assert result["verified"] is True
    assert result["rows"] == 1
    assert result["rules_version"] == "callback-review-v2"


def test_modified_output_rejected(tmp_path):
    source, report, manifest = _artifacts(tmp_path)
    report.write_bytes(report.read_bytes() + b"\n")
    with pytest.raises(ReviewVerificationError, match="output_sha256 mismatch"):
        verify_review(source, report, manifest)


def test_modified_input_rejected(tmp_path):
    source, report, manifest = _artifacts(tmp_path)
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ReviewVerificationError, match="input_sha256 mismatch"):
        verify_review(source, report, manifest)


def test_manifest_count_tampering_rejected(tmp_path):
    source, report, manifest = _artifacts(tmp_path)
    data = json.loads(manifest.read_text())
    data["output_row_count"] = 2
    manifest.write_text(json.dumps(data))
    with pytest.raises(ReviewVerificationError, match="Manifest output count mismatch"):
        verify_review(source, report, manifest)


def test_manifest_status_tampering_rejected(tmp_path):
    source, report, manifest = _artifacts(tmp_path)
    data = json.loads(manifest.read_text())
    data["status_counts"] = {"RECORD_GAP": 1}
    manifest.write_text(json.dumps(data))
    with pytest.raises(ReviewVerificationError, match="Manifest status counts mismatch"):
        verify_review(source, report, manifest)
