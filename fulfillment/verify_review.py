"""Verify local review artifacts against the generated checksum manifest.

This is an integrity consistency check, not a signature, trusted timestamp,
proof of sales, or proof that a customer consented to processing.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import hmac
import io
import json
from pathlib import Path

from .callback_review import MAX_INPUT_BYTES, MAX_ROWS, OUTPUT_COLUMNS


class ReviewVerificationError(ValueError):
    """An artifact is inconsistent, incomplete, or unsafe to verify."""


def _read_limited(path: Path, limit: int, label: str) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ReviewVerificationError(f"{label} exceeds verification size limit")
    return data


def _parse_rows(data: bytes, label: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)) or any(not name for name in headers):
            raise ReviewVerificationError(f"{label} has invalid column headers")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ReviewVerificationError(f"{label} has malformed CSV rows")
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ReviewVerificationError(f"{label} is not valid UTF-8 CSV") from exc
    return headers, rows


def verify_review(input_csv: Path, output_csv: Path, manifest_json: Path) -> dict:
    """Verify bytes, counts, output schema and classifications without exposing lead PII."""
    input_csv, output_csv, manifest_json = map(Path, (input_csv, output_csv, manifest_json))
    if input_csv.resolve() == output_csv.resolve():
        raise ReviewVerificationError("Input and output paths must be distinct")
    try:
        manifest = json.loads(_read_limited(manifest_json, 100_000, "Manifest"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewVerificationError("Manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise ReviewVerificationError("Manifest must be a JSON object")
    source = _read_limited(input_csv, MAX_INPUT_BYTES, "Input")
    reviewed = _read_limited(output_csv, 10_000_000, "Output")
    for name, content in (("input_sha256", source), ("output_sha256", reviewed)):
        expected = manifest.get(name)
        if not isinstance(expected, str) or not hmac.compare_digest(
            expected, hashlib.sha256(content).hexdigest()
        ):
            raise ReviewVerificationError(f"{name} mismatch")
    source_headers, source_rows = _parse_rows(source, "Input")
    output_headers, output_rows = _parse_rows(reviewed, "Output")
    if not {"lead_id", "inquiry_at"}.issubset(source_headers):
        raise ReviewVerificationError("Input missing required review columns")
    if output_headers != OUTPUT_COLUMNS:
        raise ReviewVerificationError("Output schema mismatch")
    if not 1 <= len(source_rows) <= MAX_ROWS:
        raise ReviewVerificationError("Input row count out of bounds")
    if len(source_rows) != len(output_rows):
        raise ReviewVerificationError("Input/output row counts differ")
    if manifest.get("source_row_count") != len(source_rows):
        raise ReviewVerificationError("Manifest source count mismatch")
    if manifest.get("output_row_count") != len(output_rows):
        raise ReviewVerificationError("Manifest output count mismatch")
    if manifest.get("status_counts") != dict(
        Counter(row["verification_status"] for row in output_rows)
    ):
        raise ReviewVerificationError("Manifest status counts mismatch")
    if manifest.get("no_external_actions") is not True:
        raise ReviewVerificationError("Missing declared no-external-actions flag")
    return {
        "verified": True,
        "rows": len(output_rows),
        "rules_version": manifest.get("rules_version", "unknown"),
        "note": "Local consistency verified; external anchoring and buyer approval are separate",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify review files against their local manifest")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_review(args.input, args.output, args.manifest), sort_keys=True))


if __name__ == "__main__":
    main()
