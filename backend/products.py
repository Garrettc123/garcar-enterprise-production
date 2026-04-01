"""Product API endpoints — what paying customers actually access."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import random
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
    deal_size: Optional[float] = None
    stage: Optional[str] = "discovery"
    notes: Optional[str] = None


@router.post("/deal-desk/analyze")
def analyze_deal(
    req: DealAnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used, limit = check_usage(user, "deal_desk", db)

    # Score the deal (production would use ML model)
    base_score = random.randint(40, 95)
    stage_bonus = {"discovery": 0, "qualification": 10, "proposal": 20, "negotiation": 30, "closed_won": 50}.get(
        req.stage, 0
    )
    size_bonus = min(15, int((req.deal_size or 0) / 10000)) if req.deal_size else 0
    score = min(100, base_score + stage_bonus + size_bonus)

    # Generate action items
    actions = []
    if score < 50:
        actions = ["Schedule discovery call", "Research company pain points", "Prepare ROI analysis"]
    elif score < 75:
        actions = ["Send case study", "Schedule demo with decision maker", "Prepare pricing proposal"]
    else:
        actions = ["Send contract", "Schedule implementation kickoff", "Introduce to CS team"]

    log_usage(user, "deal_desk", 1, db)

    return {
        "company": req.company_name,
        "score": score,
        "grade": "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
        "stage": req.stage,
        "deal_size": req.deal_size,
        "recommended_actions": actions,
        "win_probability": f"{score}%",
        "estimated_close_days": max(7, 90 - score),
        "usage": {"used": used + 1, "limit": limit},
    }


# ─── SEO CONTENT FACTORY ──────────────────────────────────

class SEORequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None
    tone: Optional[str] = "professional"
    word_count: Optional[int] = 800


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
        "meta_description": f"Learn everything about {req.topic}. Expert insights, actionable strategies, and proven frameworks for {keywords[0]}.",
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
        "seo_score": random.randint(75, 98),
        "readability_score": random.randint(70, 95),
    }

    log_usage(user, "seo_factory", req.word_count or 800, db)

    return {
        "content": content,
        "status": "generated",
        "usage": {"used": used + 1, "limit": limit},
    }


# ─── CHURN PREDICTOR ──────────────────────────────────────

class ChurnRequest(BaseModel):
    customer_id: str
    monthly_spend: Optional[float] = None
    days_since_login: Optional[int] = None
    support_tickets: Optional[int] = None
    feature_usage_pct: Optional[float] = None


@router.post("/churn-predictor/predict")
def predict_churn(
    req: ChurnRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used, limit = check_usage(user, "churn_predictor", db)

    # Churn model (production would use trained ML model)
    risk = 20.0  # base risk
    if req.days_since_login and req.days_since_login > 14:
        risk += min(30, req.days_since_login * 1.5)
    if req.support_tickets and req.support_tickets > 3:
        risk += min(20, req.support_tickets * 4)
    if req.feature_usage_pct is not None and req.feature_usage_pct < 30:
        risk += 25
    if req.monthly_spend and req.monthly_spend < 50:
        risk += 10
    risk = min(99, max(1, risk + random.uniform(-5, 5)))

    # Retention playbook
    if risk > 70:
        actions = [
            "Immediate outreach — schedule a call within 24 hours",
            "Offer 20% discount or plan upgrade trial",
            "Assign dedicated CSM",
        ]
        urgency = "critical"
    elif risk > 40:
        actions = [
            "Send re-engagement email with new feature highlights",
            "Offer onboarding refresh session",
            "Share relevant case studies",
        ]
        urgency = "medium"
    else:
        actions = [
            "Continue regular check-ins",
            "Share product updates newsletter",
            "Invite to customer community",
        ]
        urgency = "low"

    log_usage(user, "churn_predictor", 1, db)

    return {
        "customer_id": req.customer_id,
        "churn_risk_pct": round(risk, 1),
        "risk_level": urgency,
        "factors": {
            "login_recency": "high_risk" if (req.days_since_login or 0) > 14 else "ok",
            "support_load": "high_risk" if (req.support_tickets or 0) > 3 else "ok",
            "feature_adoption": "low" if (req.feature_usage_pct or 100) < 30 else "healthy",
            "revenue_risk": f"${req.monthly_spend or 0:.0f}/mo",
        },
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
