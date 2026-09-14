"""Governed Super-Fabric: scalable economic autonomy with bounded authority.

The fabric separates intelligence from authority. Agents may plan, reason,
collaborate and score opportunities freely; side effects require explicit
capability grants, budgets and policy approval. This makes scale additive
without making authority additive.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json
import uuid

SAFE_ACTIONS = {"analyze", "plan", "score", "draft", "simulate", "classify", "recommend"}
HIGH_RISK = {"send_money", "refund", "change_billing", "delete_data", "deploy_production", "change_security", "bulk_contact"}

@dataclass(frozen=True)
class Authority:
    agent: str
    allowed_actions: frozenset[str]
    budget_cents: int = 0
    max_actions: int = 10
    human_approval_required: bool = True

@dataclass
class Mission:
    id: str
    objective: str
    agent: str
    action: str
    estimated_value_cents: int
    risk: str
    approved: bool
    execution_id: str

class SuperFabric:
    """One scalable control plane for many agents and many tenants."""
    def __init__(self) -> None:
        self.authority: dict[str, Authority] = {}
        self.missions: dict[str, Mission] = {}
        self.ledger: list[dict[str, Any]] = []

    def grant(self, authority: Authority) -> None:
        self.authority[authority.agent] = authority

    def propose(self, agent: str, objective: str, action: str,
                estimated_value_cents: int = 0, risk: str = "low") -> dict[str, Any]:
        execution_id = str(uuid.uuid4())
        a = self.authority.get(agent)
        if not a:
            raise PermissionError("agent has no authority grant")
        allowed = action in a.allowed_actions
        risky = action in HIGH_RISK or risk in {"high", "critical"}
        approved = allowed and not risky and action in SAFE_ACTIONS
        if risky or not allowed:
            approved = False
        mission = Mission(str(uuid.uuid4()), objective, agent, action,
                          max(0, estimated_value_cents), risk, approved, execution_id)
        self.missions[mission.id] = mission
        self.ledger.append({"event":"mission_proposed", "mission":asdict(mission),
                            "policy":"approved" if approved else "escalated"})
        return asdict(mission)

    def authorize(self, mission_id: str, human_approved: bool = False) -> dict[str, Any]:
        m = self.missions[mission_id]
        a = self.authority[m.agent]
        if m.action in HIGH_RISK and not human_approved:
            raise PermissionError("human approval required for high-risk action")
        if m.action not in a.allowed_actions:
            raise PermissionError("action outside agent authority")
        if a.budget_cents <= 0 and m.action not in SAFE_ACTIONS:
            raise PermissionError("no side-effect budget granted")
        m.approved = True
        self.ledger.append({"event":"mission_authorized", "mission_id":mission_id,
                            "human_approved":human_approved})
        return asdict(m)

    def verify_outcome(self, mission_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
        m = self.missions[mission_id]
        digest = sha256(json.dumps(outcome, sort_keys=True, default=str).encode()).hexdigest()
        record = {"mission_id": mission_id, "execution_id": m.execution_id,
                  "verified_at": datetime.now(timezone.utc).isoformat(),
                  "outcome_hash": digest, "outcome": outcome}
        self.ledger.append({"event":"outcome_verified", **record})
        return record

    def status(self) -> dict[str, Any]:
        return {"agents_with_authority": len(self.authority),
                "missions": len(self.missions),
                "ledger_events": len(self.ledger),
                "policy": "intelligence_unbounded_within_context; authority_bounded",
                "high_risk": sorted(HIGH_RISK)}
