"""Product API endpoints — what paying customers actually access."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import logging

from database import get_db
from models import User, APIUsage
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/products", tags=["products"])

# Plan limits (monthly)
PLAN_LIMITS = {
    "free": {"deal_desk": 5, "seo_factory": 3, "churn_predictor": 10, "api_calls": 50},
    "starter": {"deal_desk": 100, "seo_factory": 50, "churn_predictor": 200, "api_calls": 1000},
    "professional": {"deal_desk": 1000, "seo_factory": 500, "churn_predictor": 2000, "api_calls": 10000},
    "enterprise": {"deal_desk": 999999, "seo_factory": 999999, "churn_predictor": 999999, "api_calls": 999999},
}


def check_usage(user: User, endpoint: str, db: Session):
    """Check if user has remaining quota for this endpoint."""
    limits = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
    limit = limits.get(endpoint, 0)

    # Count usage this month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (
        db.query(APIUsage)
        .filter(
            APIUsage.user_id == user.id,
            APIUsage.endpoint == endpoint,
            APIUsage.timestamp >= month_start,
        )
        .count()
    )

    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Usage limit reached",
                "plan": user.plan,
                "endpoint": endpoint,
                "used": used,
                "limit": limit,
                "upgrade_url": "/pricing",
            },
        )
    return used, limit


def log_usage(user: User, endpoint: str, tokens: int, db: Session):
    usage = APIUsage(user_id=user.id, endpoint=endpoint, tokens_used=tokens)
    db.add(usage)
    db.commit()


# ─── DEAL DESK ─────────────────────────────────────────────

class DealAnalysisRequest(BaseModel):
    company_name: str
    deal_size: Optional[float] = Field(None, ge=0, allow_inf_nan=False)
    stage: Optional[str] = None
    notes: Optional[str] = None


@router.post("/deal-desk/analyze")
def analyze_deal(
    req: DealAnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used, limit = check_usage(user, "deal_desk", db)

    stages = ["discovery", "qualification", "proposal", "negotiation", "closed_won"]
    stage_actions = {
        "discovery": "Document the buyer's goal",
        "qualification": "Confirm decision maker and timeline",
        "proposal": "Review the proposal with the buyer",
        "negotiation": "Resolve outstanding terms",
        "closed_won": "Confirm the delivery handoff",
    }
    index = stages.index(req.stage) if req.stage in stages else None
    score = index * 25 if index is not None else None
    actions = [stage_actions.get(req.stage, "Confirm the current deal stage")]

    log_usage(user, "deal_desk", 0, db)

    return {
        "company": req.company_name,
        "score": score,
        "grade": None,
        "score_basis": "position_in_five_reported_stages",
        "stage": req.stage,
        "deal_size": req.deal_size,
        "recommended_actions": actions,
        "win_probability": None,
        "estimated_close_days": None,
        "usage": {"used": used + 1, "limit": limit},
    }


# ─── SEO CONTENT FACTORY ──────────────────────────────────

class SEORequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None
    tone: Optional[str] = "professional"
    word_count: int = Field(800, gt=0, le=100000)


@router.post("/seo-factory/generate")
def generate_seo_content(
    req: SEORequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used, limit = check_usage(user, "seo_factory", db)

    keywords = req.keywords or [req.topic.lower()]

    # Generate content structure (production would use LLM)
    content = {
        "title": f"The Complete Guide to {req.topic}",
        "meta_description": f"Learn everything about {req.topic}. An outline covering {keywords[0]}.",
        "slug": req.topic.lower().replace(" ", "-").replace("'", ""),
        "outline": [
            {"h2": f"What is {req.topic}?", "word_count": 150},
            {"h2": f"Why {req.topic} Matters in 2026", "word_count": 200},
            {"h2": f"How to Get Started with {req.topic}", "word_count": 250},
            {"h2": f"Common {req.topic} Mistakes to Avoid", "word_count": 150},
            {"h2": f"Advanced {req.topic} Strategies", "word_count": 200},
        ],
        "target_keywords": keywords,
        "estimated_word_count": req.word_count,
        "seo_score": None,
        "readability_score": None,
    }

    per_section, remainder = divmod(req.word_count, len(content["outline"]))
    for index, section in enumerate(content["outline"]):
        section["word_count"] = per_section + int(index < remainder)

    log_usage(user, "seo_factory", 0, db)

    return {
        "content": content,
        "status": "outline_generated",
        "usage": {"used": used + 1, "limit": limit},
    }


# ─── CHURN PREDICTOR ──────────────────────────────────────

class ChurnRequest(BaseModel):
    customer_id: str
    monthly_spend: Optional[float] = Field(None, ge=0)
    days_since_login: Optional[int] = Field(None, ge=0)
    support_tickets: Optional[int] = Field(None, ge=0)
    feature_usage_pct: Optional[float] = Field(None, ge=0, le=100)


@router.post("/churn-predictor/predict")
def predict_churn(
    req: ChurnRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used, limit = check_usage(user, "churn_predictor", db)

    observed = {
        "login_recency": None if req.days_since_login is None else req.days_since_login > 14,
        "support_load": None if req.support_tickets is None else req.support_tickets > 3,
        "feature_adoption": None if req.feature_usage_pct is None else req.feature_usage_pct < 30,
    }
    signals = sum(value is True for value in observed.values())
    if signals:
        urgency = "critical" if signals > 1 else "medium"
        actions = ["Review the flagged usage or support signals with the account owner"]
    elif None in observed.values():
        urgency = "unknown"
        actions = ["Collect missing login, usage or support data"]
    else:
        urgency = "low"
        actions = ["Continue regular account reviews"]
    factors = {key: "unknown" if value is None else "flagged" if value else "within threshold"
               for key, value in observed.items()}
    factors["revenue_risk"] = "unknown" if req.monthly_spend is None else f"${req.monthly_spend:,.2f}/mo"

    log_usage(user, "churn_predictor", 0, db)

    return {
        "customer_id": req.customer_id,
        "churn_risk_pct": None,
        "risk_level": urgency,
        "flagged_signals": signals,
        "factors": factors,
        "recommended_actions": actions,
        "retention_playbook": urgency,
        "usage": {"used": used + 1, "limit": limit},
    }


@router.get("/usage")
def get_usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current month's usage across all products."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    limits = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])

    usage = {}
    for endpoint in ["deal_desk", "seo_factory", "churn_predictor"]:
        used = (
            db.query(APIUsage)
            .filter(APIUsage.user_id == user.id, APIUsage.endpoint == endpoint, APIUsage.timestamp >= month_start)
            .count()
        )
        usage[endpoint] = {"used": used, "limit": limits.get(endpoint, 0)}

    return {"plan": user.plan, "period": str(month_start.date()), "usage": usage}
