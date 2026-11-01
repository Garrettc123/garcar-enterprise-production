"""Tests for append-only ledger sequencing and Stripe webhook policy."""
import hashlib
import io
import json
from unittest.mock import Mock

import pytest
import stripe
from stripe import SignatureVerificationError
from botocore.exceptions import ClientError
from fastapi import HTTPException

from src.hash_chain import append_event
from src.stripe_reconciliation import verify_stripe_event


def locked_bucket(_s3, _bucket):
    return {"mode": "COMPLIANCE", "days": 365}


def client_error(code, operation):
    return ClientError({"Error": {"Code": code}}, operation)


def locked_json(value):
    return {
        "Body": io.BytesIO(json.dumps(value).encode("utf-8")),
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-30T00:00:00Z",
    }


def payload_hash(record):
    canonical = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_chain_append_creates_event_head_and_completion_receipt():
    s3 = Mock()
    s3.get_object.side_effect = client_error("NoSuchKey", "GetObject")
    s3.put_object.side_effect = [
        {"VersionId": "reservation-v1"},
        {"VersionId": "event-v1"},
        {"VersionId": "head-v1"},
        {"VersionId": "receipt-v1"},
    ]
    s3.head_object.return_value = {
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-30T00:00:00Z",
    }

    digest = append_event(s3, "ledger", "evt-123", {"event_type": "TEST"}, locked_bucket)

    assert len(digest) == 64
    assert s3.put_object.call_count == 4
    reservation_write = s3.put_object.call_args_list[0].kwargs
    assert "evidence/chain/idempotency/evt-123.json" == reservation_write["Key"]
    reservation_doc = json.loads(reservation_write["Body"])
    assert reservation_doc["payload_sha256"] == payload_hash({"event_type": "TEST"})

    event_write = s3.put_object.call_args_list[1].kwargs
    assert "00000000000000000001-evt-123.json" in event_write["Key"]
    head_write = s3.put_object.call_args_list[2].kwargs
    assert head_write["IfNoneMatch"] == "*"

    receipt_write = s3.put_object.call_args_list[3].kwargs
    assert receipt_write["Key"] == "evidence/chain/receipts/evt-123.json"
    receipt_doc = json.loads(receipt_write["Body"])
    assert receipt_doc["event_hash"] == digest
    assert receipt_doc["state"] == "COMMITTED"


def test_duplicate_completed_event_returns_original_hash():
    record = {"event_type": "TEST", "value": 10}
    request_hash = payload_hash(record)
    chained_record = {
        **record,
        "chain": {"sequence": 7, "previous_hash": "b" * 64},
    }
    event_hash = payload_hash(chained_record)
    stored_event = {**chained_record, "sha256": event_hash}
    s3 = Mock()
    s3.put_object.side_effect = client_error("PreconditionFailed", "PutObject")
    s3.get_object.side_effect = [
        locked_json({
            "event_id": "evt-123",
            "payload_sha256": request_hash,
            "state": "RESERVED",
        }),
        locked_json({
            "event_id": "evt-123",
            "payload_sha256": request_hash,
            "event_hash": event_hash,
            "sequence": 7,
            "state": "COMMITTED",
        }),
        locked_json(stored_event),
        locked_json({"sequence": 8, "event_hash": "c" * 64}),
    ]

    digest = append_event(s3, "ledger", "evt-123", record, locked_bucket)

    assert digest == event_hash
    assert s3.get_object.call_count == 4


def test_duplicate_event_id_with_changed_payload_is_rejected():
    original_hash = payload_hash({"event_type": "TEST", "value": 10})
    s3 = Mock()
    s3.put_object.side_effect = client_error("PreconditionFailed", "PutObject")
    s3.get_object.return_value = locked_json({
        "event_id": "evt-123",
        "payload_sha256": original_hash,
        "state": "RESERVED",
    })

    with pytest.raises(HTTPException) as duplicate:
        append_event(
            s3, "ledger", "evt-123",
            {"event_type": "TEST", "value": 11},
            locked_bucket,
        )
    assert duplicate.value.status_code == 409


def test_incomplete_reservation_fails_closed_for_reconciliation():
    record = {"event_type": "TEST"}
    request_hash = payload_hash(record)
    s3 = Mock()
    s3.put_object.side_effect = client_error("PreconditionFailed", "PutObject")
    s3.get_object.side_effect = [
        locked_json({
            "event_id": "evt-123",
            "payload_sha256": request_hash,
            "state": "RESERVED",
        }),
        client_error("NoSuchKey", "GetObject"),
    ]

    with pytest.raises(RuntimeError, match="manual reconciliation"):
        append_event(s3, "ledger", "evt-123", record, locked_bucket)


def test_chain_head_race_fails_closed():
    s3 = Mock()
    s3.get_object.side_effect = client_error("NoSuchKey", "GetObject")
    s3.put_object.side_effect = [
        {"VersionId": "reservation-v1"},
        {"VersionId": "event-v1"},
        client_error("PreconditionFailed", "PutObject"),
    ]
    s3.head_object.return_value = {
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-30T00:00:00Z",
    }
    with pytest.raises(RuntimeError, match="changed concurrently"):
        append_event(s3, "ledger", "evt-race", {"event_type": "TEST"}, locked_bucket)


def test_stripe_webhook_requires_signature_configuration():
    with pytest.raises(HTTPException) as missing:
        verify_stripe_event(b"{}", None, "")
    assert missing.value.status_code == 503


def test_stripe_webhook_rejects_bad_signature(monkeypatch):
    def reject(*_args):
        raise SignatureVerificationError("bad signature", "sig_header")
    monkeypatch.setattr(stripe.Webhook, "construct_event", reject)
    with pytest.raises(HTTPException) as invalid:
        verify_stripe_event(b"{}", "bad", "whsec_test")
    assert invalid.value.status_code == 400
