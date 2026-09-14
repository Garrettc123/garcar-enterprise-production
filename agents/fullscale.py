"""GARCAR full-scale agent control plane.

Loads the 497-agent ExportBlock inventory at runtime, deduplicates identities,
and exposes a safe dispatcher. Registry presence does not imply that an agent
has permission to perform external side effects: concrete adapters must be
registered explicitly.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
EXPORTBLOCK = ROOT / "exportblock"
NAMES_FILE = EXPORTBLOCK / "agent-names.txt"
MANIFEST_FILE = EXPORTBLOCK / "manifest.json"


class AgentControlPlane:
    def __init__(self) -> None:
        self.adapters: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self.active: dict[str, dict[str, Any]] = {}
        self.started_at = datetime.now(timezone.utc)
        self._agents = self._load_agents()

    @staticmethod
    def _read_wrapped_file(path: Path) -> dict[str, Any]:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        # The imported ExportBlock files are wrapped as {content, encoding, ...}.
        return data if isinstance(data, dict) else {"content": raw}

    def _load_agents(self) -> list[dict[str, Any]]:
        wrapped = self._read_wrapped_file(NAMES_FILE)
        names = [x.strip() for x in str(wrapped.get("content", "")).splitlines() if x.strip()]
        seen: set[str] = set()
        agents: list[dict[str, Any]] = []
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            agents.append({
                "id": f"exportblock:{name}",
                "name": name,
                "state": "available",
                "adapter": "generic",
            })
        return agents

    @property
    def agents(self) -> list[dict[str, Any]]:
        return list(self._agents)

    def get(self, name: str) -> dict[str, Any] | None:
        return next((a for a in self._agents if a["name"] == name), None)

    def register_adapter(self, name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if not self.get(name):
            raise KeyError(f"Unknown agent: {name}")
        self.adapters[name] = handler

    def activate(self, names: list[str] | None = None) -> dict[str, Any]:
        selected = self._agents if names is None else [self.get(n) for n in names]
        missing = [n for n in (names or []) if not self.get(n)]
        if missing:
            raise KeyError(f"Unknown agents: {missing}")
        now = datetime.now(timezone.utc).isoformat()
        for agent in selected:
            if agent:
                self.active[agent["name"]] = {**agent, "state": "active", "activated_at": now}
        return self.status()

    def dispatch(self, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        agent = self.get(name)
        if not agent:
            raise KeyError(f"Unknown agent: {name}")
        if name not in self.active:
            self.activate([name])
        handler = self.adapters.get(name)
        if handler is None:
            return {
                "status": "accepted",
                "execution": "capability_only",
                "agent": name,
                "message": "Agent is registered and addressable; no side-effect adapter is installed.",
                "payload": payload or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        result = handler(payload or {})
        return {"status": "completed", "execution": "adapter", "agent": name, "result": result}

    def status(self) -> dict[str, Any]:
        return {
            "total_source_records": 497,
            "unique_agents": len(self._agents),
            "active_agents": len(self.active),
            "registered_adapters": len(self.adapters),
            "source": "ExportBlock",
            "started_at": self.started_at.isoformat(),
        }


_control_plane = AgentControlPlane()


def get_control_plane() -> AgentControlPlane:
    return _control_plane
