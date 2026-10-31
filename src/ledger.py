import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError


class LedgerError(RuntimeError):
    pass


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def seal_record(
    record: dict[str, Any], bucket: str, region: str, retention_days: int
) -> dict[str, str]:
    if not bucket:
        raise LedgerError("S3_LEDGER_BUCKET is required")
    if retention_days < 1:
        raise LedgerError("A positive retention period is required")

    digest = hashlib.sha256(canonical_json(record)).hexdigest()
    key = f"records/{digest[:2]}/{digest}.json"
    client = boto3.client("s3", region_name=region)
    sealed_at = datetime.now(timezone.utc)
    envelope = canonical_json(
        {
            "record": record,
            "sha256": digest,
            "sealed_at": sealed_at.isoformat(),
            "hash_algorithm": "SHA-256",
        }
    )

    for attempt in range(3):
        try:
            response = client.put_object(
                Bucket=bucket,
                Key=key,
                Body=envelope,
                ContentType="application/json",
                ChecksumAlgorithm="SHA256",
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=sealed_at
                + timedelta(days=retention_days),
                IfNoneMatch="*",
            )
            return {
                "sha256": digest,
                "key": key,
                "version_id": response.get("VersionId", ""),
                "result": "sealed",
            }
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode"
            )
            code = exc.response.get("Error", {}).get("Code", "")
            if status == 412 or code == "PreconditionFailed":
                try:
                    head = client.head_object(Bucket=bucket, Key=key)
                except ClientError as head_exc:
                    raise LedgerError(
                        "Existing ledger object could not be verified"
                    ) from head_exc
                return {
                    "sha256": digest,
                    "key": key,
                    "version_id": head.get("VersionId", ""),
                    "result": "already_sealed",
                }
            if status == 409 or code == "ConditionalRequestConflict":
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                    continue
            raise LedgerError("Immutable ledger write failed") from exc

    raise LedgerError("Immutable ledger write failed after conditional retries")
