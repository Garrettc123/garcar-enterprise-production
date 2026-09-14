"""Scale contract for the Garcar Super-Fabric.

Scale increases throughput, not authority. Workers remain tenant-scoped,
policy-scoped and auditable. Execution is real by default; safety comes from
capability grants, budgets, idempotency and the policy governor—not simulation.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ScaleContract:
    max_concurrency: int = 1000
    max_queue_depth: int = 10000
    default_timeout_seconds: int = 90
    execution_mode: str = "live"
    tenant_isolation: str = "required"
    idempotency: str = "required"
    audit_trail: str = "required"
    human_gate_for_high_risk: bool = True
    production_merge: str = "human_only"

CONTRACT = ScaleContract()
