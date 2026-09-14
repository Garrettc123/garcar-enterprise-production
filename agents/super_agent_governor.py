"""Economic + safety governor for live Garcar super-agent execution."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    mode: str
    reason: str
    risk: str
    approval_required: bool
    max_spend_cents: int
    reversible: bool

class SuperAgentGovernor:
    SAFE_ACTIONS={"analyze","plan","evaluate","respond","communicate","coordinate","optimize","draft","score","classify","recommend"}
    HIGH_RISK_ACTIONS={"charge_customer","refund","payout","transfer_money","delete_data","publish_legal","change_production","send_bulk_message","change_billing"}

    def decide(self, *, objective:str, action:str, requested_spend_cents:int=0, reversible:bool=True, human_approval:bool=False)->PolicyDecision:
        action=action.strip().lower(); spend=max(0,int(requested_spend_cents))
        if action in self.HIGH_RISK_ACTIONS and not human_approval:
            return PolicyDecision(False,"approval_required","High-risk economic or production action requires explicit human approval.","critical",True,0,reversible)
        if action not in self.SAFE_ACTIONS and not human_approval:
            return PolicyDecision(False,"approval_required","Unclassified side effect requires explicit human approval.","high",True,0,reversible)
        ceiling=2500 if reversible else 0
        if spend>ceiling:
            return PolicyDecision(False,"budget_exceeded","Requested spend exceeds autonomous execution budget.","high",True,ceiling,reversible)
        return PolicyDecision(True,"autonomous",f"Approved for bounded objective: {objective}","low",False,ceiling,reversible)

    def envelope(self,decision:PolicyDecision,objective:str)->dict[str,Any]:
        return {"economic_objective":objective,"governor":asdict(decision),"money_movement":"never implicit"}
