"""Tests for evidence and signed approval policy."""
from datetime import datetime, timedelta, timezone

from src.evidence import build_contractor_profile
from src.governance import OwnerApproval, sign_approval, verify_approval


def make_approval():
    now = datetime.now(timezone.utc)
    return OwnerApproval(
        approval_id="approval-0001",
        permit_id="DFW-123",
        decision="approve_for_review",
        allowed_actions=["prepare_outreach_draft"],
        evidence_refs=["sha256:abc123"],
        issued_at=now - timedelta(seconds=5),
        expires_at=now + timedelta(minutes=10),
        nonce="nonce-value-123456",
    )


def test_no_evidence_provider_means_unknown_not_invented():
    profile = build_contractor_profile("contractor-123")
    assert profile.evidence_state == "UNKNOWN"
    assert profile.rating is None
    assert profile.completed_project_count is None
    assert profile.evidence == []


def test_signed_approval_is_scoped_to_one_permit():
    approval = make_approval()
    signature = sign_approval(approval, "test-signing-key")
    assert verify_approval(approval, signature, "test-signing-key", "DFW-123")
    assert not verify_approval(approval, signature, "test-signing-key", "OTHER-PERMIT")


def test_modified_approval_invalidates_signature():
    approval = make_approval()
    signature = sign_approval(approval, "test-signing-key")
    changed = approval.model_copy(update={"allowed_actions": ["export_review_packet"]})
    assert not verify_approval(changed, signature, "test-signing-key", "DFW-123")


def test_expired_or_rejected_approval_is_not_accepted():
    approval = make_approval()
    signature = sign_approval(approval, "test-signing-key")
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert not verify_approval(approval, signature, "test-signing-key", "DFW-123", now=future)
    rejected = approval.model_copy(update={"decision": "reject"})
    rejected_signature = sign_approval(rejected, "test-signing-key")
    assert not verify_approval(rejected, rejected_signature, "test-signing-key", "DFW-123")
