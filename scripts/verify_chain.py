"""Verify the committed S3 ledger chain and flag immutable orphan events."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any

import boto3

ZERO_HASH = "0" * 64


def _retention_is_compliant(response: dict[str, Any]) -> bool:
    return (
        response.get("ObjectLockMode") == "COMPLIANCE"
        and response.get("ObjectLockRetainUntilDate") is not None
    )


def _canonical_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify(bucket: str, region: str) -> tuple[bool, str]:
    """Verify the chain reachable from head.json; never mistake orphan writes for commits.

    A failed S3 head compare-and-swap can leave an immutable event object that is not
    referenced by the committed head. Such an object is reported as an orphan and
    causes verification to fail closed until an operator reconciles it.
    """
    s3 = boto3.client("s3", region_name=region)
    paginator = s3.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix="evidence/chain/events/"):
        keys.extend(item["Key"] for item in page.get("Contents", []))
    keys.sort()

    # Index validated objects by their content hash. Sequence sorting alone is unsafe:
    # competing writers can leave multiple immutable objects with the same sequence.
    events_by_hash: dict[str, dict[str, Any]] = {}
    for key in keys:
        response = s3.get_object(Bucket=bucket, Key=key)
        if not _retention_is_compliant(response):
            return False, f"COMPLIANCE retention missing at {key}"

        record = json.loads(response["Body"].read())
        recorded_hash = record.pop("sha256", None)
        calculated_hash = _canonical_hash(record)
        metadata_hash = response.get("Metadata", {}).get("sha256")
        if recorded_hash != calculated_hash or metadata_hash != calculated_hash:
            return False, f"content hash mismatch at {key}"

        chain = record.get("chain")
        if not isinstance(chain, dict):
            return False, f"chain metadata missing at {key}"
        sequence = chain.get("sequence")
        previous_hash = chain.get("previous_hash")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            return False, f"invalid sequence at {key}"
        if (
            not isinstance(previous_hash, str)
            or len(previous_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in previous_hash)
        ):
            return False, f"invalid previous hash at {key}"
        if calculated_hash in events_by_hash:
            return False, f"duplicate content hash found at {key}"

        events_by_hash[calculated_hash] = {
            "key": key,
            "sequence": sequence,
            "previous_hash": previous_hash,
        }

    head_response = s3.get_object(Bucket=bucket, Key="evidence/chain/head.json")
    if not _retention_is_compliant(head_response):
        return False, "chain head COMPLIANCE retention missing"
    head = json.loads(head_response["Body"].read())
    head_sequence = head.get("sequence")
    head_hash = head.get("event_hash")
    if not isinstance(head_sequence, int) or isinstance(head_sequence, bool) or head_sequence < 1:
        return False, "chain head sequence is invalid"
    if (
        not isinstance(head_hash, str)
        or len(head_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in head_hash)
    ):
        return False, "chain head hash is invalid"

    # Walk backward from the committed head. Only objects reachable through previous_hash
    # are committed chain events; other retained objects are orphans, not chain members.
    current_hash = head_hash
    expected_sequence = head_sequence
    linked_keys: set[str] = set()
    visited_hashes: set[str] = set()

    while current_hash != ZERO_HASH:
        if current_hash in visited_hashes:
            return False, "cycle detected in ledger chain"
        visited_hashes.add(current_hash)
        event = events_by_hash.get(current_hash)
        if event is None:
            return False, f"chain head references missing event at sequence {expected_sequence}"
        if event["sequence"] != expected_sequence:
            return False, f"sequence mismatch at {event['key']}"
        linked_keys.add(event["key"])
        current_hash = event["previous_hash"]
        expected_sequence -= 1
        if expected_sequence < 0:
            return False, "chain contains more links than its head sequence"

    if expected_sequence != 0:
        return False, "chain does not terminate at the zero hash"

    orphan_count = len(keys) - len(linked_keys)
    if orphan_count:
        return False, (
            f"committed chain is valid for {head_sequence} events, but "
            f"{orphan_count} unlinked immutable event object(s) require manual reconciliation"
        )
    if len(linked_keys) != head_sequence:
        return False, "committed event count does not match chain head sequence"

    return True, f"verified {head_sequence} committed events; no orphan objects"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    try:
        valid, detail = verify(args.bucket, args.region)
    except Exception as exc:
        print(f"VERIFY_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(detail)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
