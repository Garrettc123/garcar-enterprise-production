"""SQLAlchemy ORM models."""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import secrets

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _gen_api_key():
    return f"gce_{secrets.token_hex(24)}"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    plan = Column(String(50), default="free")  # free | starter | professional | enterprise
    api_key = Column(String(100), unique=True, default=_gen_api_key)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    payments = relationship("Payment", back_populates="user")
    api_usage = relationship("APIUsage", back_populates="user")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_payment_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="usd")
    status = Column(String(50), nullable=False)  # succeeded | pending | failed | refunded
    plan = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="payments")


class APIUsage(Base):
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    endpoint = Column(String(255), nullable=False)
    tokens_used = Column(Integer, default=0)
    timestamp = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="api_usage")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    source = Column(String(100), default="website")  # website | api | referral | ad
    status = Column(String(50), default="new")  # new | contacted | qualified | converted | lost
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    converted_at = Column(DateTime, nullable=True)

    nurture_steps = relationship("NurtureStep", back_populates="lead")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    sequence_name = Column(String(100), nullable=False)  # e.g. "welcome_drip"
    step_number = Column(Integer, nullable=False)  # 1, 2, 3...
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=False)
    delay_hours = Column(Integer, default=0)  # hours after previous step
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)


class NurtureStep(Base):
    __tablename__ = "nurture_steps"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=False)
    sequence_name = Column(String(100), nullable=False)
    step_number = Column(Integer, nullable=False)
    status = Column(String(50), default="pending")  # pending | sent | failed | skipped
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    lead = relationship("Lead", back_populates="nurture_steps")
    template = relationship("EmailTemplate")
