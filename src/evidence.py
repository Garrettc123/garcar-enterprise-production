"""Evidence-backed enrichment contracts.

No provider is configured by default. Missing source records remain unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_uri: HttpUrl
    source_name: str = Field(min_length=2, max_length=200)
    claim: str = Field(min_length=1, max_length=1000)
    observed_at: datetime
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    subject_id: str = Field(min_length=1, max_length=200)


class ContractorProfile(BaseModel):
    contractor_id: str
    evidence: list[EvidenceRecord] = []
    rating: float | None = None
    completed_project_count: int | None = None
    evidence_state: str = "UNKNOWN"


class EvidenceProvider(Protocol):
    def get_contractor_evidence(self, contractor_id: str) -> list[EvidenceRecord]: ...


class NoEvidenceProvider:
    """Safe default: no enrichment is asserted without a connected provider."""

    def get_contractor_evidence(self, contractor_id: str) -> list[EvidenceRecord]:
        return []


def build_contractor_profile(
    contractor_id: str, provider: EvidenceProvider | None = None
) -> ContractorProfile:
    selected = provider or NoEvidenceProvider()
    records = selected.get_contractor_evidence(contractor_id)
    # Evidence is surfaced, not converted into a rating or project count.
    return ContractorProfile(
        contractor_id=contractor_id,
        evidence=records,
        rating=None,
        completed_project_count=None,
        evidence_state="SOURCE_RECORDS_AVAILABLE" if records else "UNKNOWN",
    )
