"""Governed full-scale agent runtime.

Loads the ExportBlock registry as capability metadata and provides a safe
adapter boundary. Registry presence never implies that an agent performed an
external action. Real adapters must be explicitly registered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

Adapter = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class AgentExecution:
    agent: str
    execution_id: str
    state: str
    started_at: str
    result: dict[str, Any] = field(default_factory=dict)


class FullScaleAgentRuntime:
    def __init__(self, registry: list[dict[str, Any]]):
        self.registry = registry
        self.adapters: dict[str, Adapter] = {}
        self.executions: list[AgentExecution] = []

    def register_adapter(self, agent: str, adapter: Adapter) -> None:
        if not any(a.get("name") == agent for a in self.registry):
            raise ValueError(f"Unknown registered agent: {agent}")
        self.adapters[agent] = adapter

    def inventory(self) -> dict[str, Any]:
        unique = {}
        for agent in self.registry:
            unique.setdefault(agent.get("name"), agent)
        return {
            "source_records": len(self.registry),
            "unique_agents": len(unique),
            "adapter_count": len(self.adapters),
            "runnable_agents": sorted(self.adapters),
            "capability_only": sorted(set(unique) - set(self.adapters)),
        }

    async def dispatch(self, agent: str, context: dict[str, Any] | None = None) -> AgentExecution:
        if agent not in self.adapters:
            raise RuntimeError(
                f"Agent {agent} is capability-only; register a real adapter before execution"
            )
        execution_id = f"{agent}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        execution = AgentExecution(
            agent=agent,
            execution_id=execution_id,
            state="running",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.executions.append(execution)
        try:
            execution.result = await self.adapters[agent](context or {})
            execution.state = "succeeded"
        except Exception as exc:
            execution.state = "failed"
            execution.result = {"error": str(exc)}
            raise
        return execution

    async def activate_all(self) -> dict[str, Any]:
        """Activate the control plane without pretending unimplemented agents ran."""
        return {
            "status": "control_plane_active",
            **self.inventory(),
            "execution_policy": {
                "external_side_effects": "adapter_required",
                "production_merge": "human_only",
                "secrets_changes": "forbidden",
                "workflow_changes": "explicit_review_required",
            },
        }
