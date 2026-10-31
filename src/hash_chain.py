"""Optimistic, append-only S3 hash-chain writer.

A failed head compare-and-swap leaves an unlinked immutable event. The caller must fail
closed; reconciliation tooling must inspect such orphan records before resuming writes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from botocore.exceptions import ClientError
from fastapi import HTTPException

ZERO_HASH = "0" * 64


def _read_head(s3: Any, bucket: str) -> tuple[dict[str, Any], str | None]:
    try:
        result = s3.get_object(Bucket=bucket, Key="evidence/chain/head.json")
        if result.get("ObjectLockMode") != "COMPLIANCE" or not result.get("ObjectLockRetainUntilDate"):
            raise RuntimeError("Current chain head lacks verified COMPLIANCE retention")
        head = json.loads(result["Body"].read())
        if not isinstance(head.get("sequence"), int) or head["sequence"] < 1:
            raise RuntimeError("Current chain head sequence is invalid")
        event_hash = head.get("event_hash", "")
        if len(event_hash) != 64 or any(ch not in "0123456789abcdef" for ch in event_hash):
            raise RuntimeError("Current chain head hash is invalid")
        return head, result.get("ETag")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return {"sequence": 0, "event_hash": ZERO_HASH}, None
        raise


def _verify_version(s3: Any, bucket: str, key: str, version_id: str) -> None:
    stored = s3.head_object(Bucket=bucket, Key=key, VersionId=version_id)
    if stored.get("ObjectLockMode") != "COMPLIANCE" or not stored.get("ObjectLockRetainUntilDate"):
        raise RuntimeError("Stored chain object lacks verified COMPLIANCE retention")


def append_event(
    s3: Any,
    bucket: str,
    event_id: str,
    record: dict[str, Any],
    verify_bucket: Callable[[Any, str], Any],
) -> str:
    verify_bucket(s3, bucket)

    reservation_key = f"evidence/chain/idempotency/{event_id}.json"
    try:
        reservation = s3.put_object(
            Bucket=bucket, Key=reservation_key, Body=b"reserved",
            ContentType="text/plain", IfNoneMatch="*",
        )
        reservation_version = reservation.get("VersionId")
        if not reservation_version:
            raise RuntimeError("S3 did not return an idempotency reservation version")
        _verify_version(s3, bucket, reservation_key, reservation_version)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"PreconditionFailed", "412", "ConditionalRequestConflict"}:
            raise HTTPException(status_code=409, detail="event_id already exists") from exc
        raise

    head, etag = _read_head(s3, bucket)
    sequence = int(head.get("sequence", 0)) + 1
    previous_hash = head.get("event_hash", ZERO_HASH)
    chained_record = {
        **record,
        "chain": {"sequence": sequence, "previous_hash": previous_hash},
    }
    canonical = json.dumps(
        chained_record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    body = json.dumps(
        {**chained_record, "sha256": digest},
        sort_keys=True, indent=2,
    ).encode("utf-8")
    event_key = f"evidence/chain/events/{sequence:020d}-{event_id}.json"
    result = s3.put_object(
        Bucket=bucket, Key=event_key, Body=body,
        ContentType="application/json",
        Metadata={"sha256": digest, "event-id": event_id, "sequence": str(sequence)},
        IfNoneMatch="*",
    )
    event_version = result.get("VersionId")
    if not event_version:
        raise RuntimeError("S3 did not return a chained event version")
    _verify_version(s3, bucket, event_key, event_version)

    new_head = json.dumps(
        {"sequence": sequence, "event_id": event_id, "event_hash": digest},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    kwargs = {
        "Bucket": bucket, "Key": "evidence/chain/head.json", "Body": new_head,
        "ContentType": "application/json", "Metadata": {"event-hash": digest},
    }
    if etag:
        kwargs["IfMatch"] = etag
    else:
        kwargs["IfNoneMatch"] = "*"
    try:
        head_result = s3.put_object(**kwargs)
    except ClientError as exc:
        raise RuntimeError(
            "Ledger chain head changed concurrently; orphan event requires reconciliation"
        ) from exc
    head_version = head_result.get("VersionId")
    if not head_version:
        raise RuntimeError("S3 did not return a chain-head version")
    _verify_version(s3, bucket, "evidence/chain/head.json", head_version)
    return digest
