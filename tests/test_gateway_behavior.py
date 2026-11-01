"""Behavioral tests for fail-closed policy and evidence integrity."""
import base64
import hashlib
import io
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from botocore.exceptions import ClientError

from src import main


def sample_payload():
    return main.PermitPayload(
        event_id=uuid4(),
        permit_id="DFW-123",
        municipality="Cleburne",
        contractor_name="Example Roofing",
        property_address="100 Main Street, Cleburne, TX",
        valuation=125000,
        description="Roof replacement",
        filing_date="2026-10-30",
    )


def test_vault_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(main, "VAULT_ADDR", None)
    monkeypatch.setattr(main, "VAULT_ROLE_ID", None)
    monkeypatch.setattr(main, "VAULT_SECRET_ID", None)
    with pytest.raises(RuntimeError, match="refusing fallback"):
        main._vault_client()


def valid_runtime_values():
    return {
        "S3_LEDGER_BUCKET": "garcar-ledger-test",
        "OWNER_APPROVAL_PUBLIC_KEY": base64.b64encode(bytes(range(32))).decode("ascii"),
        "STRIPE_WEBHOOK_SECRET": "whsec_" + "s" * 32,
        "API_BEARER_TOKEN": "t" * 48,
    }


def test_runtime_config_accepts_valid_secrets_without_mutating_them():
    values = valid_runtime_values()
    validated = main.validate_runtime_config(values)
    assert validated == values


def test_runtime_config_requires_every_secret_and_bucket():
    values = valid_runtime_values()
    del values["STRIPE_WEBHOOK_SECRET"]
    with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
        main.validate_runtime_config(values)


def test_runtime_config_rejects_short_api_token():
    values = valid_runtime_values()
    values["API_BEARER_TOKEN"] = "short"
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        main.validate_runtime_config(values)


def test_runtime_config_rejects_invalid_owner_public_key():
    values = valid_runtime_values()
    values["OWNER_APPROVAL_PUBLIC_KEY"] = "not-base64"
    with pytest.raises(RuntimeError, match="base64-encoded"):
        main.validate_runtime_config(values)


def test_runtime_config_rejects_wrong_owner_public_key_size():
    values = valid_runtime_values()
    values["OWNER_APPROVAL_PUBLIC_KEY"] = base64.b64encode(b"short").decode("ascii")
    with pytest.raises(RuntimeError, match="exactly 32 bytes"):
        main.validate_runtime_config(values)


def test_runtime_config_rejects_invalid_stripe_webhook_secret():
    values = valid_runtime_values()
    values["STRIPE_WEBHOOK_SECRET"] = "wrong-format"
    with pytest.raises(RuntimeError, match="invalid format"):
        main.validate_runtime_config(values)


def test_authentication_rejects_missing_or_wrong_token(monkeypatch):
    monkeypatch.setattr(main, "load_runtime_config", lambda: {"API_BEARER_TOKEN": "expected-secret"})
    with pytest.raises(HTTPException) as missing:
        main.require_api_auth(None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as wrong:
        main.require_api_auth("Bearer wrong")
    assert wrong.value.status_code == 401
    assert main.require_api_auth("Bearer expected-secret") is None


def test_authentication_fails_closed_when_vault_unavailable(monkeypatch):
    def unavailable():
        raise RuntimeError("vault unavailable")
    monkeypatch.setattr(main, "load_runtime_config", unavailable)
    with pytest.raises(HTTPException) as unavailable_response:
        main.require_api_auth("Bearer any-token")
    assert unavailable_response.value.status_code == 503


def configure_bucket_security(s3):
    s3.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }
    s3.get_bucket_encryption.return_value = {
        "ServerSideEncryptionConfiguration": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        }
    }


def test_worm_verification_requires_compliance_and_versioning():
    s3 = Mock()
    s3.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}},
        }
    }
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    configure_bucket_security(s3)
    assert main.verify_worm_configuration(s3, "ledger") == {
        "mode": "COMPLIANCE",
        "days": 365,
        "years": None,
        "public_access_blocked": True,
        "encryption": ["AES256"],
    }
    s3.get_bucket_versioning.return_value = {"Status": "Suspended"}
    with pytest.raises(RuntimeError, match="versioning"):
        main.verify_worm_configuration(s3, "ledger")


def test_worm_verification_requires_public_access_blocking():
    s3 = Mock()
    s3.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}},
        }
    }
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    configure_bucket_security(s3)
    s3.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": True,
        }
    }
    with pytest.raises(RuntimeError, match="Block Public Access"):
        main.verify_worm_configuration(s3, "ledger")


def test_worm_verification_requires_encryption():
    s3 = Mock()
    s3.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}},
        }
    }
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    configure_bucket_security(s3)
    s3.get_bucket_encryption.return_value = {
        "ServerSideEncryptionConfiguration": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "NONE"}}]
        }
    }
    with pytest.raises(RuntimeError, match="server-side encryption"):
        main.verify_worm_configuration(s3, "ledger")


def test_worm_verification_fails_when_object_lock_missing():
    s3 = Mock()
    s3.get_object_lock_configuration.side_effect = ClientError(
        {"Error": {"Code": "ObjectLockConfigurationNotFoundError"}},
        "GetObjectLockConfiguration",
    )
    with pytest.raises(RuntimeError, match="Unable to verify"):
        main.verify_worm_configuration(s3, "ledger")


def test_review_is_never_auto_approved_or_sent():
    result = main.prepare_review(sample_payload(), "a" * 64)
    assert result["status"] == "HUMAN_REVIEW_REQUIRED"
    assert result["approval"] == "NOT_GRANTED"
    assert result["outreach"] == "NOT_SENT"
    assert result["contractor_rating"] is None
    assert result["past_projects_count"] is None


def test_duplicate_s3_event_returns_original_ledger_hash(monkeypatch):
    payload = sample_payload()
    record = {
        "schema_version": 1,
        "event_id": str(payload.event_id),
        "event_type": "PERMIT_INGESTED",
        "permit": payload.model_dump(mode="json"),
    }
    canonical = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    request_hash = hashlib.sha256(canonical).hexdigest()

    s3 = Mock()
    s3.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}},
        }
    }
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    configure_bucket_security(s3)
    s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "PreconditionFailed"}},
        "PutObject",
    )
    chained_record = {
        **record,
        "chain": {"sequence": 4, "previous_hash": "c" * 64},
    }
    event_digest = hashlib.sha256(json.dumps(
        chained_record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    stored_event = {**chained_record, "sha256": event_digest}
    def locked_response(value):
        return {
            "Body": io.BytesIO(json.dumps(value).encode("utf-8")),
            "ObjectLockMode": "COMPLIANCE",
            "ObjectLockRetainUntilDate": "2027-10-30T00:00:00Z",
        }
    s3.get_object.side_effect = [
        locked_response({
            "event_id": str(payload.event_id),
            "payload_sha256": request_hash,
            "state": "RESERVED",
        }),
        locked_response({
            "event_id": str(payload.event_id),
            "payload_sha256": request_hash,
            "event_hash": event_digest,
            "sequence": 4,
            "state": "COMMITTED",
        }),
        locked_response(stored_event),
        locked_response({"sequence": 4, "event_hash": event_digest}),
    ]
    monkeypatch.setattr(main, "_s3_client", lambda: s3)

    digest = main.seal_event(payload, {"S3_LEDGER_BUCKET": "ledger"})

    assert digest == event_digest
    assert s3.get_object.call_count == 4


def test_payload_rejects_unexpected_fields():
    data = sample_payload().model_dump()
    data["is_approved"] = True
    with pytest.raises(Exception):
        main.PermitPayload(**data)
