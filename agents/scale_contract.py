"""Scale contract for the Garcar Super-Fabric.

The contract is intentionally independent of infrastructure. Horizontal scale
must increase throughput, not authority. Each worker remains tenant-scoped,
policy-scoped and auditable.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ScaleContract:
    max_concurrency: int = 1000
    max_queue_depth: int = 10000
    default_timeout_seconds: int = 90
    default_dry_run: bool = True
    tenant_isolation: str = "required"
    idempotency: str = "required"
    audit_trail: str = "required"
    human_gate_for_high_risk: bool = True
    production_merge: str = "human_only"

CONTRACT = ScaleContract()
