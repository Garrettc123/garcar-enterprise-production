"""Verify S3 ledger chain sequence, content hashes, head pointer, and retention."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

import boto3

ZERO_HASH = "0" * 64


def verify(bucket: str, region: str) -> tuple[bool, str]:
    s3 = boto3.client("s3", region_name=region)
    events = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="evidence/chain/events/"):
        for item in page.get("Contents", []):
            events.append(item["Key"])
    events.sort()

    previous_hash = ZERO_HASH
    expected_sequence = 1
    for key in events:
        response = s3.get_object(Bucket=bucket, Key=key)
        record = json.loads(response["Body"].read())
        recorded_hash = record.pop("sha256", None)
        chain = record.get("chain", {})
        canonical = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        calculated = hashlib.sha256(canonical).hexdigest()
        if chain.get("sequence") != expected_sequence:
            return False, f"sequence gap at {key}"
        if chain.get("previous_hash") != previous_hash:
            return False, f"previous hash mismatch at {key}"
        if recorded_hash != calculated or response.get("Metadata", {}).get("sha256") != calculated:
            return False, f"content hash mismatch at {key}"
        if response.get("ObjectLockMode") != "COMPLIANCE" or not response.get("ObjectLockRetainUntilDate"):
            return False, f"retention missing at {key}"
        previous_hash = calculated
        expected_sequence += 1

    head_response = s3.get_object(Bucket=bucket, Key="evidence/chain/head.json")
    head = json.loads(head_response["Body"].read())
    if head.get("sequence") != expected_sequence - 1 or head.get("event_hash") != previous_hash:
        return False, "chain head does not match verified event sequence"
    if head_response.get("ObjectLockMode") != "COMPLIANCE" or not head_response.get("ObjectLockRetainUntilDate"):
        return False, "chain head retention missing"
    return True, f"verified {expected_sequence - 1} events"


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
