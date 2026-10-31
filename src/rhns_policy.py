"""Deterministic RHNS policy gate; evidence is required and missing values fail closed."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PolicyContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    municipality: str
    valuation: float = Field(ge=0)
    maximum_authorized_valuation: float | None = Field(default=None, ge=0)
    permit_source_verified: bool = False
    contractor_identity_verified: bool = False
    authority_verified: bool = False
    owner_approval_verified: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    requested_action: Literal["prepare_outreach_draft", "send_outreach", "move_funds"] = "prepare_outreach_draft"


def evaluate_rhns_policy(context: PolicyContext) -> dict[str, object]:
    reasons: list[str] = []
    if not context.permit_source_verified:
        reasons.append("permit_source_not_verified")
    if not context.contractor_identity_verified:
        reasons.append("contractor_identity_not_verified")
    if not context.authority_verified:
        reasons.append("authority_not_verified")
    if not context.owner_approval_verified:
        reasons.append("owner_approval_not_verified")
    if not context.evidence_refs:
        reasons.append("evidence_references_missing")
    if context.maximum_authorized_valuation is None:
        reasons.append("authorized_budget_missing")
    elif context.valuation > context.maximum_authorized_valuation:
        reasons.append("valuation_exceeds_authorized_budget")
    if context.requested_action != "prepare_outreach_draft":
        reasons.append("action_not_permitted_by_this_service")
    return {
        "decision": "ELIGIBLE_FOR_DRAFT_PREPARATION" if not reasons else "HUMAN_REVIEW_REQUIRED",
        "reasons": reasons,
        "risk_score": None,
        "external_action": "NOT_EXECUTED",
    }
