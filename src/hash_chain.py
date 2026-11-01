"""Optimistic, append-only S3 hash-chain writer with verified idempotency receipts.

A failed head compare-and-swap leaves an unlinked immutable event. The caller fails
closed; reconciliation tooling must inspect such orphan records before writes resume.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from botocore.exceptions import ClientError
from fastapi import HTTPException

ZERO_HASH = "0" * 64


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _read_locked_json(s3: Any, bucket: str, key: str) -> dict[str, Any] | None:
    """Read a JSON object and require visible COMPLIANCE retention metadata."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise

    if (
        response.get("ObjectLockMode") != "COMPLIANCE"
        or not response.get("ObjectLockRetainUntilDate")
    ):
        raise RuntimeError(f"Stored object {key} lacks verified COMPLIANCE retention")
    value = json.loads(response["Body"].read())
    if not isinstance(value, dict):
        raise RuntimeError(f"Stored object {key} is not a JSON object")
    return value


def _read_head(s3: Any, bucket: str) -> tuple[dict[str, Any], str | None]:
    try:
        result = s3.get_object(Bucket=bucket, Key="evidence/chain/head.json")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return {"sequence": 0, "event_hash": ZERO_HASH}, None
        raise

    if (
        result.get("ObjectLockMode") != "COMPLIANCE"
        or not result.get("ObjectLockRetainUntilDate")
    ):
        raise RuntimeError("Current chain head lacks verified COMPLIANCE retention")
    head = json.loads(result["Body"].read())
    sequence = head.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise RuntimeError("Current chain head sequence is invalid")
    event_hash = head.get("event_hash", "")
    if (
        not isinstance(event_hash, str)
        or len(event_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in event_hash)
    ):
        raise RuntimeError("Current chain head hash is invalid")
    return head, result.get("ETag")


def _verify_version(s3: Any, bucket: str, key: str, version_id: str) -> None:
    stored = s3.head_object(Bucket=bucket, Key=key, VersionId=version_id)
    if (
        stored.get("ObjectLockMode") != "COMPLIANCE"
        or not stored.get("ObjectLockRetainUntilDate")
    ):
        raise RuntimeError("Stored chain object lacks verified COMPLIANCE retention")


def _read_completed_receipt(
    s3: Any,
    bucket: str,
    event_id: str,
    payload_hash: str,
) -> str:
    reservation_key = f"evidence/chain/idempotency/{event_id}.json"
    reservation = _read_locked_json(s3, bucket, reservation_key)
    if reservation is None:
        raise RuntimeError("Event reservation conflicted but cannot be read")
    if reservation.get("event_id") != event_id or reservation.get("state") != "RESERVED":
        raise RuntimeError("Event idempotency reservation is invalid")
    if reservation.get("payload_sha256") != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="event_id was already reserved for a different payload",
        )

    receipt_key = f"evidence/chain/receipts/{event_id}.json"
    receipt = _read_locked_json(s3, bucket, receipt_key)
    if receipt is None:
        raise RuntimeError(
            "Event ID is reserved but has no completion receipt; manual reconciliation is required"
        )
    if (
        receipt.get("event_id") != event_id
        or receipt.get("state") != "COMMITTED"
        or receipt.get("payload_sha256") != payload_hash
    ):
        raise RuntimeError("Event completion receipt does not match its reservation")

    sequence = receipt.get("sequence")
    event_hash = receipt.get("event_hash")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise RuntimeError("Event completion receipt sequence is invalid")
    if (
        not isinstance(event_hash, str)
        or len(event_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in event_hash)
    ):
        raise RuntimeError("Event completion receipt hash is invalid")

    event_key = f"evidence/chain/events/{sequence:020d}-{event_id}.json"
    stored_event = _read_locked_json(s3, bucket, event_key)
    if stored_event is None:
        raise RuntimeError("Committed event is missing; manual reconciliation is required")
    stored_hash = stored_event.pop("sha256", None)
    actual_hash = hashlib.sha256(_canonical_json(stored_event)).hexdigest()
    chain = stored_event.get("chain", {})
    payload_record = {name: value for name, value in stored_event.items() if name != "chain"}
    if (
        stored_hash != event_hash
        or actual_hash != event_hash
        or chain.get("sequence") != sequence
        or hashlib.sha256(_canonical_json(payload_record)).hexdigest() != payload_hash
    ):
        raise RuntimeError("Stored event does not match its completion receipt")

    head, _etag = _read_head(s3, bucket)
    if head.get("sequence", 0) < sequence:
        raise RuntimeError("Chain head does not include the completed event")
    if head.get("sequence") == sequence and head.get("event_hash") != event_hash:
        raise RuntimeError("Chain head conflicts with the completion receipt")
    return event_hash


def append_event(
    s3: Any,
    bucket: str,
    event_id: str,
    record: dict[str, Any],
    verify_bucket: Callable[[Any, str], Any],
) -> str:
    verify_bucket(s3, bucket)
    payload_hash = hashlib.sha256(_canonical_json(record)).hexdigest()

    reservation_key = f"evidence/chain/idempotency/{event_id}.json"
    reservation_body = _canonical_json({
        "event_id": event_id,
        "payload_sha256": payload_hash,
        "state": "RESERVED",
    })
    try:
        reservation = s3.put_object(
            Bucket=bucket,
            Key=reservation_key,
            Body=reservation_body,
            ContentType="application/json",
            IfNoneMatch="*",
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}:
            return _read_completed_receipt(s3, bucket, event_id, payload_hash)
        raise

    reservation_version = reservation.get("VersionId")
    if not reservation_version:
        raise RuntimeError("S3 did not return an idempotency reservation version")
    _verify_version(s3, bucket, reservation_key, reservation_version)

    head, etag = _read_head(s3, bucket)
    sequence = int(head.get("sequence", 0)) + 1
    previous_hash = head.get("event_hash", ZERO_HASH)
    chained_record = {
        **record,
        "chain": {"sequence": sequence, "previous_hash": previous_hash},
    }
    digest = hashlib.sha256(_canonical_json(chained_record)).hexdigest()
    body = json.dumps(
        {**chained_record, "sha256": digest},
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")
    event_key = f"evidence/chain/events/{sequence:020d}-{event_id}.json"
    result = s3.put_object(
        Bucket=bucket,
        Key=event_key,
        Body=body,
        ContentType="application/json",
        Metadata={"sha256": digest, "event-id": event_id, "sequence": str(sequence)},
        IfNoneMatch="*",
    )
    event_version = result.get("VersionId")
    if not event_version:
        raise RuntimeError("S3 did not return a chained event version")
    _verify_version(s3, bucket, event_key, event_version)

    new_head = _canonical_json({
        "sequence": sequence,
        "event_id": event_id,
        "event_hash": digest,
    })
    kwargs = {
        "Bucket": bucket,
        "Key": "evidence/chain/head.json",
        "Body": new_head,
        "ContentType": "application/json",
        "Metadata": {"event-hash": digest},
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

    receipt_key = f"evidence/chain/receipts/{event_id}.json"
    receipt_body = _canonical_json({
        "event_id": event_id,
        "payload_sha256": payload_hash,
        "event_hash": digest,
        "sequence": sequence,
        "state": "COMMITTED",
    })
    receipt_result = s3.put_object(
        Bucket=bucket,
        Key=receipt_key,
        Body=receipt_body,
        ContentType="application/json",
        IfNoneMatch="*",
    )
    receipt_version = receipt_result.get("VersionId")
    if not receipt_version:
        raise RuntimeError("S3 did not return an idempotency receipt version")
    _verify_version(s3, bucket, receipt_key, receipt_version)
    return digest
