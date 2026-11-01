"""Behavioral tests for fail-closed policy and evidence integrity."""
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


def test_duplicate_s3_event_is_rejected(monkeypatch):
    payload = sample_payload()
    s3 = Mock()
    s3.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}},
        }
    }
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "PreconditionFailed"}},
        "PutObject",
    )
    monkeypatch.setattr(main, "_s3_client", lambda: s3)
    with pytest.raises(HTTPException) as duplicate:
        main.seal_event(payload, {"S3_LEDGER_BUCKET": "ledger"})
    assert duplicate.value.status_code == 409


def test_payload_rejects_unexpected_fields():
    data = sample_payload().model_dump()
    data["is_approved"] = True
    with pytest.raises(Exception):
        main.PermitPayload(**data)
