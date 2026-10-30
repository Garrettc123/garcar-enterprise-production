import hashlib, json
from datetime import datetime, timedelta, timezone
from typing import Any
import boto3
from botocore.exceptions import ClientError

class LedgerError(RuntimeError): pass

def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def seal_record(record: dict[str, Any], bucket: str, region: str, retention_days: int) -> dict[str, str]:
    if not bucket:
        raise LedgerError("S3_LEDGER_BUCKET is required")
    body = canonical_json(record)
    digest = hashlib.sha256(body).hexdigest()
    key = f"records/{digest[:2]}/{digest}.json"
    client = boto3.client("s3", region_name=region)
    retain_until = datetime.now(timezone.utc) + timedelta(days=retention_days)
    envelope = canonical_json({"record": record, "sha256": digest, "sealed_at": datetime.now(timezone.utc).isoformat()})
    try:
        response = client.put_object(
            Bucket=bucket, Key=key, Body=envelope, ContentType="application/json",
            ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=retain_until,
            IfNoneMatch="*",
        )
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 412:
            head = client.head_object(Bucket=bucket, Key=key)
            return {"sha256": digest, "key": key, "version_id": head.get("VersionId", ""), "result": "already_sealed"}
        raise LedgerError("Immutable ledger write failed") from exc
    return {"sha256": digest, "key": key, "version_id": response.get("VersionId", ""), "result": "sealed"}
