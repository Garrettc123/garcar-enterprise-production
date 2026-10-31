from src.orchestrator import PermitInput, evaluate_permit

def valid_permit():
    return PermitInput(
        permit_id="P-1",
        municipality="DFW",
        contractor_name="Example Co",
        property_address="1 Main St",
        valuation=1000,
        filing_date="2026-10-30",
    )

def test_permit_defaults_to_review_without_evidence():
    result = evaluate_permit(valid_permit())
    assert result["approved"] is False
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["outreach_draft"] is None
    assert "source_uri" in result["missing_evidence"]

def test_permit_rejects_non_finite_valuation():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PermitInput(
            permit_id="P-2", municipality="DFW", contractor_name="Example Co",
            property_address="1 Main St", valuation=float("nan"), filing_date="2026-10-30",
        )
