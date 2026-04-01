"""Lead capture and nurture system."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import logging

from database import get_db
from models import Lead, User
from auth import get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/leads", tags=["leads"])


class LeadCaptureRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    source: Optional[str] = "website"


class LeadResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    source: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/capture", response_model=LeadResponse)
def capture_lead(req: LeadCaptureRequest, db: Session = Depends(get_db)):
    """Public endpoint — captures a lead from landing page or API."""
    existing = db.query(Lead).filter(Lead.email == req.email).first()
    if existing:
        # Update source if different, don't create duplicate
        if req.name and not existing.name:
            existing.name = req.name
            db.commit()
            db.refresh(existing)
        return existing

    lead = Lead(
        email=req.email,
        name=req.name,
        source=req.source,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    logger.info(f"New lead captured: {lead.email} from {lead.source}")
    return lead


@router.get("/", response_model=list[LeadResponse])
def list_leads(
    status: Optional[str] = None,
    limit: int = 100,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin-only: list all captured leads."""
    query = db.query(Lead).order_by(Lead.created_at.desc())
    if status:
        query = query.filter(Lead.status == status)
    return query.limit(limit).all()


@router.post("/{lead_id}/status")
def update_lead_status(
    lead_id: int,
    new_status: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin-only: update lead status."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    valid_statuses = ["new", "contacted", "qualified", "converted", "lost"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    lead.status = new_status
    if new_status == "converted":
        lead.converted_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": f"Lead {lead.email} updated to {new_status}"}


@router.get("/stats")
def lead_stats(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Admin-only: lead pipeline statistics."""
    total = db.query(Lead).count()
    by_status = {}
    for s in ["new", "contacted", "qualified", "converted", "lost"]:
        by_status[s] = db.query(Lead).filter(Lead.status == s).count()

    by_source = {}
    for source_row in db.query(Lead.source).distinct():
        src = source_row[0]
        by_source[src] = db.query(Lead).filter(Lead.source == src).count()

    return {
        "total": total,
        "by_status": by_status,
        "by_source": by_source,
        "conversion_rate": round(by_status.get("converted", 0) / max(total, 1) * 100, 1),
    }
