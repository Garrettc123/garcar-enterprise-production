"""Approval and Stripe webhook routes; these record evidence only."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from src.governance import OwnerApproval, verify_approval
from src.hash_chain import append_event
from src.stripe_reconciliation import verify_stripe_event
from src.main import load_runtime_config, require_api_auth, _s3_client, verify_worm_configuration

router = APIRouter()


def record_control_event(bucket: str, key: str, record: dict[str, Any]) -> str:
    # The final path component is the stable event identifier; all control events share
    # the same ordered chain as permit intake.
    event_id = key.rsplit("/", 1)[-1].removesuffix(".json")
    s3 = _s3_client()
    return append_event(s3, bucket, event_id, record, verify_worm_configuration)


@router.post("/approvals/permits/{permit_id}", dependencies=[Depends(require_api_auth)])
async def record_owner_approval(
    permit_id: str,
    approval: OwnerApproval,
    signature: str = Header(default="", alias="X-Garcar-Approval-Signature"),
) -> dict[str, Any]:
    try:
        config = load_runtime_config()
        valid = verify_approval(
            approval, signature, config.get("OWNER_APPROVAL_PUBLIC_KEY", ""), permit_id
        )
        if not valid:
            raise HTTPException(status_code=403, detail="Owner approval signature or scope is invalid")
        digest = record_control_event(
            config["S3_LEDGER_BUCKET"],
            f"evidence/approvals/{approval.approval_id}.json",
            {
                "event_type": "OWNER_APPROVAL_RECORDED",
                "approval": approval.model_dump(mode="json"),
                "execution_state": "NOT_EXECUTED",
            },
        )
        return {
            "status": "APPROVAL_RECORDED_NOT_EXECUTED",
            "approval_id": approval.approval_id,
            "ledger_hash": digest,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Approval ledger unavailable") from exc


@router.post("/webhook/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, Any]:
    try:
        config = load_runtime_config()
        event = verify_stripe_event(
            await request.body(),
            stripe_signature,
            config.get("STRIPE_WEBHOOK_SECRET", ""),
        )
        digest = record_control_event(
            config["S3_LEDGER_BUCKET"],
            f"evidence/stripe-events/{event['event_id']}.json",
            {"event_type": "STRIPE_EVENT_RECONCILED", "stripe_event": event},
        )
        return {
            "status": "RECORDED_NOT_ACTIONED",
            "event_id": event["event_id"],
            "ledger_hash": digest,
            "funds_moved": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Stripe event reconciliation unavailable") from exc
