from src.orchestrator import PermitInput, evaluate_permit

def test_permit_defaults_to_review_without_evidence():
    permit = PermitInput(permit_id="P-1", municipality="DFW", contractor_name="Example Co",
        property_address="1 Main St", valuation=1000, filing_date="2026-10-30")
    result = evaluate_permit(permit)
    assert result["approved"] is False
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["outreach_draft"] is None
