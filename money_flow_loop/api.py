"""
FastAPI router for the Money Flow Loop.
Mount this in backend/main.py to expose the organism to the rest of the stack.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from money_flow_loop.orchestrator import MoneyFlowOrchestrator, LoopStage

router = APIRouter(prefix="/api/money-flow", tags=["money-flow-loop"])


class AttentionIngest(BaseModel):
    source: str = Field(..., description="linkedin_founder | seo_content | customer_referral | demo_request | ...")
    email: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AdvanceRequest(BaseModel):
    prospect_id: str
    target_stage: str  # trust | trial | conversion | expansion | referral


class CloseLoopRequest(BaseModel):
    customer_id: str
    outcome: Dict[str, Any]


@router.post("/ingest")
def ingest_attention(payload: AttentionIngest, db: Session = Depends(get_db)):
    """Entry point: new attention arrives."""
    orch = MoneyFlowOrchestrator(db)
    return orch.ingest_attention(
        source=payload.source,
        email=payload.email,
        phone=payload.phone,
        metadata=payload.metadata,
    )


@router.post("/advance")
def advance_stage(payload: AdvanceRequest, db: Session = Depends(get_db)):
    """Manually or automatically advance a prospect."""
    try:
        stage = LoopStage(payload.target_stage)
    except ValueError:
        raise HTTPException(400, f"Invalid stage. Choose from: {[s.value for s in LoopStage]}")

    orch = MoneyFlowOrchestrator(db)
    return orch.advance(payload.prospect_id, stage)


@router.post("/close-loop")
def close_the_loop(payload: CloseLoopRequest, db: Session = Depends(get_db)):
    """Turn a successful customer into new acquisition fuel."""
    orch = MoneyFlowOrchestrator(db)
    return orch.close_the_loop(payload.customer_id, payload.outcome)


@router.get("/health")
def loop_health(db: Session = Depends(get_db)):
    """Organism status."""
    orch = MoneyFlowOrchestrator(db)
    return orch.health()
