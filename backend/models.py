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
