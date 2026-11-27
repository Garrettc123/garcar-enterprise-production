"""Strict input contracts: unknown property valuations are never silently inferred."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class PropertyType(str, Enum):
    SINGLE_FAMILY = "single_family"
    MULTI_FAMILY = "multi_family"
    LAND = "land"
    COMMERCIAL = "commercial"

class EvidenceField(str, Enum):
    ASKING_PRICE = "asking_price"
    ARV = "arv"
    REPAIRS = "repairs"
    OWNERSHIP = "ownership"
    TITLE = "title"
    COMPARABLE = "comparable"
    BUYER_FUNDS = "buyer_funds"
    OTHER = "other"

class PropertyIn(StrictModel):
    street_address: str = Field(min_length=3, max_length=200)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    postal_code: str = Field(min_length=5, max_length=10)
    county: str = Field(min_length=2, max_length=100)
    property_type: PropertyType
    asking_price: Money
    source_url: HttpUrl
    observed_at: datetime
    operator_notes: str = Field(default="", max_length=2000)

    @field_validator("observed_at")
    @classmethod
    def must_have_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("observed_at must include a UTC offset")
        if v > datetime.now(timezone.utc):
            raise ValueError("observed_at cannot be in the future")
        return v

    @field_validator("state")
    @classmethod
    def uppercase_state(cls, v: str) -> str:
        return v.upper()

class EvidenceIn(StrictModel):
    field: EvidenceField
    source_url: HttpUrl
    observed_at: datetime
    note: str = Field(min_length=4, max_length=3000)
    reviewed_by: str | None = Field(default=None, max_length=120)
    # reviewed_by is a user-entered assertion, not an independent verification.

    @field_validator("observed_at")
    @classmethod
    def valid_date(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None or v > datetime.now(timezone.utc):
            raise ValueError("observed_at must be timezone aware and not future-dated")
        return v

class UnderwritingIn(StrictModel):
    arv: PositiveMoney
    repairs: Money
    closing_costs: Money
    holding_costs: Money
    financing_costs: Money
    reserve: Money
    buyer_target_profit: Money
    proposed_assignment_fee: Money
    selling_cost_rate: Decimal = Field(ge=0, lt=1, max_digits=5, decimal_places=4)
    heuristic_arv_fraction: Decimal = Field(default=Decimal("0.70"), gt=0, le=1, max_digits=5, decimal_places=4)

class BuyerIn(StrictModel):
    label: str = Field(min_length=2, max_length=150)
    counties: list[str] = Field(min_length=1, max_length=25)
    property_types: list[PropertyType] = Field(min_length=1)
    max_acquisition_price: PositiveMoney
    criteria_source_url: HttpUrl
    verified_at: datetime
    status: str = Field(default="research_only", pattern=r"^(research_only|criteria_reviewed)$")

    @field_validator("verified_at")
    @classmethod
    def valid_date(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None or v > datetime.now(timezone.utc):
            raise ValueError("verified_at must be timezone aware and not future-dated")
        return v

    @field_validator("counties")
    @classmethod
    def nonempty_counties(cls, v: list[str]) -> list[str]:
        if not all(1 < len(c.strip()) <= 100 for c in v):
            raise ValueError("counties must be nonblank")
        return [x.strip() for x in v]

class DecisionIn(StrictModel):
    decision: str = Field(pattern=r"^(approve_research|reject_research)$")
    reviewer: str = Field(min_length=2, max_length=120)
    rationale: str = Field(min_length=12, max_length=2000)

class ReviewStatus(str, Enum):
    DRAFT = "draft"
    RESEARCH_APPROVED = "research_approved"
    RESEARCH_REJECTED = "research_rejected"

class UnderwritingResult(StrictModel):
    asking_price: Money
    formula_mao: Money
    seventy_percent_rule_mao: Money
    maximum_allowable_offer: Money
    headroom_vs_asking: Decimal
    estimated_buyer_profit_at_asking: Decimal
    potential_assignment_fee: Money
    viable_under_assumptions: bool
    disclaimer: str = "Research estimate only; not an appraisal, legal advice, or authorization to make an offer."
