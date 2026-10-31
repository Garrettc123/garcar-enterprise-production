"""Verify a stored ledger event's canonical SHA-256 digest."""
import argparse
import hashlib
import json
import sys

import boto3


def verify(bucket: str, key: str, region: str) -> bool:
    s3 = boto3.client("s3", region_name=region)
    response = s3.get_object(Bucket=bucket, Key=key)
    record = json.loads(response["Body"].read())
    recorded_digest = record.pop("sha256", None)
    canonical = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    calculated_digest = hashlib.sha256(canonical).hexdigest()
    metadata_digest = response.get("Metadata", {}).get("sha256")
    return (
        isinstance(recorded_digest, str)
        and recorded_digest == calculated_digest
        and metadata_digest == calculated_digest
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    try:
        valid = verify(args.bucket, args.key, args.region)
    except Exception as exc:
        print(f"VERIFY_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2
    print("VALID" if valid else "INVALID")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
