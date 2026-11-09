"""Verify the committed S3 ledger chain, idempotency receipts, and retention."""
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


def _list_keys(s3: Any, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(item["Key"] for item in page.get("Contents", []))
    return sorted(keys)


def _load_locked_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    response = s3.get_object(Bucket=bucket, Key=key)
    if not _retention_is_compliant(response):
        raise RuntimeError(f"COMPLIANCE retention missing at {key}")
    value = json.loads(response["Body"].read())
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid JSON object at {key}")
    return value


def _event_id_from_key(key: str, prefix: str) -> str | None:
    if not key.startswith(prefix):
        return None
    filename = key.rsplit("/", 1)[-1]
    if not filename.endswith(".json"):
        return None
    stem = filename[:-5]
    if prefix == "evidence/chain/events/":
        if len(stem) < 22 or not stem[:20].isdigit() or stem[20] != "-":
            return None
        return stem[21:]
    return stem


def verify(bucket: str, region: str) -> tuple[bool, str]:
    """Verify the chain reachable from head.json; fail on orphans or incomplete receipts."""
    s3 = boto3.client("s3", region_name=region)
    event_prefix = "evidence/chain/events/"
    reservation_prefix = "evidence/chain/idempotency/"
    receipt_prefix = "evidence/chain/receipts/"

    keys = _list_keys(s3, bucket, event_prefix)
    events_by_hash: dict[str, dict[str, Any]] = {}
    event_by_id: dict[str, dict[str, Any]] = {}

    for key in keys:
        response = s3.get_object(Bucket=bucket, Key=key)
        if not _retention_is_compliant(response):
            return False, f"COMPLIANCE retention missing at {key}"

        record = json.loads(response["Body"].read())
        if not isinstance(record, dict):
            return False, f"invalid event JSON at {key}"
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

        event_id = _event_id_from_key(key, event_prefix)
        if not event_id:
            return False, f"event key is malformed: {key}"
        if calculated_hash in events_by_hash or event_id in event_by_id:
            return False, f"duplicate ledger event identity at {key}"

        payload_record = {name: value for name, value in record.items() if name != "chain"}
        events_by_hash[calculated_hash] = {
            "key": key,
            "event_id": event_id,
            "sequence": sequence,
            "previous_hash": previous_hash,
            "payload_sha256": _canonical_hash(payload_record),
            "event_hash": calculated_hash,
        }
        event_by_id[event_id] = events_by_hash[calculated_hash]

    head_response = s3.get_object(Bucket=bucket, Key="evidence/chain/head.json")
    if not _retention_is_compliant(head_response):
        return False, "chain head COMPLIANCE retention missing"
    head = json.loads(head_response["Body"].read())
    if not isinstance(head, dict):
        return False, "chain head JSON is invalid"
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

    try:
        reservation_keys = _list_keys(s3, bucket, reservation_prefix)
        receipt_keys = _list_keys(s3, bucket, receipt_prefix)
        reservations = {
            _event_id_from_key(key, reservation_prefix): _load_locked_json(s3, bucket, key)
            for key in reservation_keys
        }
        receipts = {
            _event_id_from_key(key, receipt_prefix): _load_locked_json(s3, bucket, key)
            for key in receipt_keys
        }
    except Exception as exc:
        return False, f"unable to verify idempotency records: {type(exc).__name__}"

    event_ids = set(event_by_id)
    if set(reservations) != event_ids:
        return False, "idempotency reservations do not match committed ledger events"
    if set(receipts) != event_ids:
        return False, "completion receipts do not match committed ledger events"

    for event_id, event in event_by_id.items():
        reservation = reservations[event_id]
        receipt = receipts[event_id]
        payload_hash = event["payload_sha256"]
        if reservation.get("event_id") != event_id or reservation.get("state") != "RESERVED":
            return False, f"invalid idempotency reservation for {event_id}"
        if reservation.get("payload_sha256") != payload_hash:
            return False, f"reservation payload hash mismatch for {event_id}"
        if receipt.get("event_id") != event_id or receipt.get("state") != "COMMITTED":
            return False, f"invalid completion receipt for {event_id}"
        if receipt.get("payload_sha256") != payload_hash:
            return False, f"receipt payload hash mismatch for {event_id}"
        if receipt.get("event_hash") != event["event_hash"]:
            return False, f"receipt event hash mismatch for {event_id}"
        if receipt.get("sequence") != event["sequence"]:
            return False, f"receipt sequence mismatch for {event_id}"

    return True, f"verified {head_sequence} committed events, receipts, and retention; no orphans"


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
