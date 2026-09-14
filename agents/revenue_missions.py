"""Revenue mission planner for governed, verifiable revenue execution."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any

@dataclass(frozen=True)
class RevenueMission:
    channel:str
    objective:str
    action:str
    measurable_outcome:str
    required_adapter:str
    risk:str

CHANNELS=(
("lead_recovery","recover missed leads","qualify_and_contact","qualified_conversation","crm_outreach","medium"),
("appointment_reactivation","reactivate dormant prospects","reactivate_pipeline","booked_appointment","crm_outreach","medium"),
("invoice_collection","collect outstanding invoices","request_payment","payment_received","billing","high"),
("upsell","increase customer value","identify_and_offer_upsell","accepted_offer","crm_outreach","medium"),
("referral","generate referred business","request_referral","qualified_referral","crm_outreach","medium"),
("outbound","create new qualified opportunities","prospect_and_contact","qualified_lead","prospecting","medium"),
("revenue_recovery","recover failed transactions","retry_or_recover_payment","recovered_payment","billing","high"),
("retention","prevent avoidable churn","intervene_on_churn_risk","retained_account","crm_outreach","medium"),
("automation_service","sell Garcar automation","qualify_and_close_service","paid_customer","checkout","high"),
("audit_service","sell revenue-leak audits","sell_audit","paid_audit","checkout","medium"),
)

def build_missions(objective:str="maximize verified revenue") -> list[dict[str,Any]]:
    return [asdict(RevenueMission(c,objective,a,o,adapter,risk)) for c,_,a,o,adapter,risk in CHANNELS]
