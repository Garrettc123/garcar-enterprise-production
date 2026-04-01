"""Admin dashboard API — metrics, customers, revenue."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from database import get_db
from models import User, Payment, APIUsage, Lead
from auth import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/metrics")
def dashboard_metrics(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Core business metrics."""
    total_users = db.query(User).count()
    active_paid = db.query(User).filter(User.plan != "free", User.is_active == True).count()

    # MRR calculation
    plan_prices = {"starter": 49, "professional": 149, "enterprise": 499}
    mrr = 0.0
    for plan, price in plan_prices.items():
        count = db.query(User).filter(User.plan == plan, User.is_active == True).count()
        mrr += count * price

    # Total revenue
    total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "succeeded").scalar() or 0

    # Leads
    total_leads = db.query(Lead).count()
    new_leads_7d = (
        db.query(Lead)
        .filter(Lead.created_at >= datetime.now(timezone.utc) - timedelta(days=7))
        .count()
    )

    # API usage today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    api_calls_today = db.query(APIUsage).filter(APIUsage.timestamp >= today_start).count()

    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "total_revenue": total_revenue,
        "total_users": total_users,
        "active_paid_users": active_paid,
        "total_leads": total_leads,
        "new_leads_7d": new_leads_7d,
        "api_calls_today": api_calls_today,
        "plan_breakdown": {
            plan: db.query(User).filter(User.plan == plan).count()
            for plan in ["free", "starter", "professional", "enterprise"]
        },
    }


@router.get("/customers")
def list_customers(
    plan: str = None,
    limit: int = 100,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all customers with their subscription info."""
    query = db.query(User).order_by(User.created_at.desc())
    if plan:
        query = query.filter(User.plan == plan)

    users = query.limit(limit).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "plan": u.plan,
            "is_active": u.is_active,
            "created_at": str(u.created_at),
            "total_payments": sum(p.amount for p in u.payments if p.status == "succeeded"),
            "api_calls": len(u.api_usage),
        }
        for u in users
    ]


@router.get("/revenue")
def revenue_over_time(
    days: int = 30,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Revenue data for charting."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    payments = (
        db.query(Payment)
        .filter(Payment.status == "succeeded", Payment.created_at >= since)
        .order_by(Payment.created_at)
        .all()
    )

    daily = {}
    for p in payments:
        day = str(p.created_at.date()) if p.created_at else "unknown"
        daily[day] = daily.get(day, 0) + p.amount

    return {
        "period_days": days,
        "total": sum(daily.values()),
        "daily": daily,
        "payments": [
            {
                "id": p.id,
                "amount": p.amount,
                "plan": p.plan,
                "status": p.status,
                "date": str(p.created_at),
            }
            for p in payments
        ],
    }


@router.get("/health")
def system_health(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """System health overview."""
    import stripe as stripe_lib
    import os

    stripe_ok = bool(os.getenv("STRIPE_SECRET_KEY"))

    return {
        "database": "connected",
        "stripe": "connected" if stripe_ok else "not configured — set STRIPE_SECRET_KEY",
        "users_table": db.query(User).count(),
        "payments_table": db.query(Payment).count(),
        "leads_table": db.query(Lead).count(),
        "api_usage_table": db.query(APIUsage).count(),
    }
