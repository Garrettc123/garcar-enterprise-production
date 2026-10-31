"""Tests for deterministic RHNS policy decisions."""
from src.rhns_policy import PolicyContext, evaluate_rhns_policy


def test_missing_evidence_and_authority_fail_closed():
    result = evaluate_rhns_policy(
        PolicyContext(municipality="Cleburne", valuation=50000)
    )
    assert result["decision"] == "HUMAN_REVIEW_REQUIRED"
    assert "permit_source_not_verified" in result["reasons"]
    assert "owner_approval_not_verified" in result["reasons"]
    assert result["risk_score"] is None
    assert result["external_action"] == "NOT_EXECUTED"


def test_complete_evidence_only_qualifies_for_draft_preparation():
    result = evaluate_rhns_policy(
        PolicyContext(
            municipality="Cleburne",
            valuation=50000,
            maximum_authorized_valuation=75000,
            permit_source_verified=True,
            contractor_identity_verified=True,
            authority_verified=True,
            owner_approval_verified=True,
            evidence_refs=["https://example.gov/permit/123"],
            requested_action="prepare_outreach_draft",
        )
    )
    assert result["decision"] == "ELIGIBLE_FOR_DRAFT_PREPARATION"
    assert result["external_action"] == "NOT_EXECUTED"


def test_send_outreach_and_move_funds_are_never_permitted():
    for action in ("send_outreach", "move_funds"):
        result = evaluate_rhns_policy(
            PolicyContext(
                municipality="Cleburne",
                valuation=1,
                maximum_authorized_valuation=10,
                permit_source_verified=True,
                contractor_identity_verified=True,
                authority_verified=True,
                owner_approval_verified=True,
                evidence_refs=["https://example.gov/source"],
                requested_action=action,
            )
        )
        assert result["decision"] == "HUMAN_REVIEW_REQUIRED"
        assert "action_not_permitted_by_this_service" in result["reasons"]
