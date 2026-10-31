from typing import Any
from pydantic import BaseModel, Field

class PermitInput(BaseModel):
    permit_id: str = Field(min_length=1, max_length=128)
    municipality: str = Field(min_length=1, max_length=128)
    contractor_name: str = Field(min_length=1, max_length=256)
    property_address: str = Field(min_length=1, max_length=512)
    valuation: float = Field(gt=0, le=100_000_000, allow_inf_nan=False)
    description: str = Field(default="", max_length=10000)
    filing_date: str = Field(min_length=8, max_length=32)

def evaluate_permit(permit: PermitInput, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = evidence or {}
    required = ("source_uri", "source_timestamp", "contractor_identity_verified")
    missing = [field for field in required if not evidence.get(field)]
    return {
        "decision": "REVIEW_REQUIRED",
        "approved": False,
        "risk_score": None,
        "missing_evidence": missing,
        "outreach_draft": None,
        "reason": "Autonomous approval is disabled until evidence and a versioned policy are independently verified.",
    }
