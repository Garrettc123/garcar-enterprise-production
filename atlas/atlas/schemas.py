from __future__ import annotations

from pydantic import BaseModel, Field


class ShopIntake(BaseModel):
    shop: str
    trade: str
    city: str
    owner: str = ""
    sources: str = "Google, Facebook, missed call, referral, website form"
    ticket: int = 4500
    jobs_week: int = 8
    close_rate: float = 0.35


class NamedLeak(BaseModel):
    name: str
    where: str
    monthly_cost: int
    fix: str


class LeakReport(BaseModel):
    shop: str
    first_response_minutes: int = 90
    leaks: list[NamedLeak] = Field(default_factory=list)
    monthly_leak_total: int = 0
    first_workflow: str = "Missed-call SMS in under 60 seconds with a booking link."


class AuditPacket(BaseModel):
    markdown: str
    outreach_sms: str
    sku_audit: str
    sku_sprint: str
    gate: str = "HUMAN_SEND_REQUIRED"
