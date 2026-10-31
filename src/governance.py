"""Cryptographically scoped owner approvals.

This module validates a signed approval statement. It does not execute the approved action.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OwnerApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    approval_id: str = Field(min_length=8, max_length=100)
    permit_id: str = Field(min_length=1, max_length=100)
    decision: Literal["approve_for_review", "reject"]
    allowed_actions: list[Literal["prepare_outreach_draft", "export_review_packet"]] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1, max_length=20)
    issued_at: datetime
    expires_at: datetime
    nonce: str = Field(min_length=16, max_length=128)


def canonical_approval(approval: OwnerApproval) -> bytes:
    return json.dumps(
        approval.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sign_approval(approval: OwnerApproval, signing_key: str) -> str:
    if not signing_key:
        raise ValueError("Owner approval signing key is not configured")
    return hmac.new(signing_key.encode(), canonical_approval(approval), hashlib.sha256).hexdigest()


def verify_approval(
    approval: OwnerApproval,
    signature: str,
    signing_key: str,
    expected_permit_id: str,
    now: datetime | None = None,
) -> bool:
    if not signing_key or not signature:
        return False
    current = now or datetime.now(timezone.utc)
    if approval.permit_id != expected_permit_id or approval.decision != "approve_for_review":
        return False
    if approval.issued_at > current or approval.expires_at <= current:
        return False
    expected = sign_approval(approval, signing_key)
    return hmac.compare_digest(expected, signature)
