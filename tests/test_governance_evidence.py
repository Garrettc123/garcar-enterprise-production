"""Tests for evidence defaults and asymmetric owner-approval verification."""
import base64
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.evidence import build_contractor_profile
from src.governance import OwnerApproval, canonical_approval, verify_approval


def make_approval():
    now = datetime.now(timezone.utc)
    return OwnerApproval(
        approval_id="approval-0001",
        permit_id="DFW-123",
        decision="approve_for_review",
        allowed_actions=["prepare_outreach_draft"],
        evidence_refs=["sha256:" + "a" * 64],
        issued_at=now - timedelta(seconds=5),
        expires_at=now + timedelta(minutes=10),
        nonce="nonce-value-123456",
    )


def make_keypair():
    private = Ed25519PrivateKey.generate()
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, base64.b64encode(public_bytes).decode("ascii")


def sign(approval, private):
    return base64.b64encode(private.sign(canonical_approval(approval))).decode("ascii")


def test_no_evidence_provider_means_unknown_not_invented():
    profile = build_contractor_profile("contractor-123")
    assert profile.evidence_state == "UNKNOWN"
    assert profile.rating is None
    assert profile.completed_project_count is None
    assert profile.evidence == []


def test_signed_approval_is_scoped_to_one_permit():
    approval = make_approval()
    private, public = make_keypair()
    signature = sign(approval, private)
    assert verify_approval(approval, signature, public, "DFW-123")
    assert not verify_approval(approval, signature, public, "OTHER-PERMIT")


def test_modified_approval_invalidates_signature():
    approval = make_approval()
    private, public = make_keypair()
    signature = sign(approval, private)
    changed = approval.model_copy(update={"allowed_actions": ["export_review_packet"]})
    assert not verify_approval(changed, signature, public, "DFW-123")


def test_expired_or_rejected_approval_is_not_accepted():
    approval = make_approval()
    private, public = make_keypair()
    signature = sign(approval, private)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert not verify_approval(approval, signature, public, "DFW-123", now=future)
    rejected = approval.model_copy(update={"decision": "reject"})
    rejected_signature = sign(rejected, private)
    assert not verify_approval(rejected, rejected_signature, public, "DFW-123")
