"""Public-key verification for scoped owner approvals.

The API holds only an Ed25519 public key. The private signing key remains offline with
the owner and is never loaded by the application.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field


class OwnerApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    approval_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    permit_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
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


def verify_approval(
    approval: OwnerApproval,
    signature: str,
    public_key_b64: str,
    expected_permit_id: str,
    now: datetime | None = None,
) -> bool:
    if not public_key_b64 or not signature:
        return False
    current = now or datetime.now(timezone.utc)
    if approval.permit_id != expected_permit_id or approval.decision != "approve_for_review":
        return False
    if approval.issued_at > current or approval.expires_at <= current:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(public_key_b64, validate=True)
        )
        public_key.verify(
            base64.b64decode(signature, validate=True),
            canonical_approval(approval),
        )
        return True
    except (InvalidSignature, ValueError):
        return False
