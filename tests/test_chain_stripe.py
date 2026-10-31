"""Tests for append-only ledger sequencing and Stripe webhook policy."""
import pytest
import stripe
from botocore.exceptions import ClientError
from fastapi import HTTPException

from src.hash_chain import append_event
from src.stripe_reconciliation import verify_stripe_event


def locked_bucket(_s3, _bucket):
    return {"mode": "COMPLIANCE", "days": 365}


def client_error(code, operation):
    return ClientError({"Error": {"Code": code}}, operation)


def test_chain_append_creates_event_and_advances_head():
    s3 = Mock()
    s3.get_object.side_effect = client_error("NoSuchKey", "GetObject")
    s3.put_object.side_effect = [
        {"VersionId": "reservation-v1"},
        {"VersionId": "event-v1"},
        {"VersionId": "head-v1"},
    ]
    s3.head_object.return_value = {
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-30T00:00:00Z",
    }
    digest = append_event(s3, "ledger", "evt-123", {"event_type": "TEST"}, locked_bucket)
    assert len(digest) == 64
    assert s3.put_object.call_count == 3
    event_write = s3.put_object.call_args_list[1].kwargs
    assert "00000000000000000001-evt-123.json" in event_write["Key"]
    head_write = s3.put_object.call_args_list[2].kwargs
    assert head_write["IfNoneMatch"] == "*"


def test_duplicate_chain_event_id_is_rejected():
    s3 = Mock()
    s3.put_object.side_effect = client_error("PreconditionFailed", "PutObject")
    with pytest.raises(HTTPException) as duplicate:
        append_event(s3, "ledger", "evt-123", {"event_type": "TEST"}, locked_bucket)
    assert duplicate.value.status_code == 409


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
        raise stripe.error.SignatureVerificationError("bad signature", "sig_header")
    monkeypatch.setattr(stripe.Webhook, "construct_event", reject)
    with pytest.raises(HTTPException) as invalid:
        verify_stripe_event(b"{}", "bad", "whsec_test")
    assert invalid.value.status_code == 400
