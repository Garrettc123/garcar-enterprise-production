"""
Garcar Enterprise — Agent Network
=================================
The living lattice of specialized, autonomous agents.

Heavy orchestrator imports are lazy so modules like sales_fleet can run
without requiring the full ExportBlock inventory on every import.
"""

__all__ = [
    "AGENTS",
    "get_agent",
    "list_by_vertical",
    "list_by_type",
    "AgentOrchestrator",
]


def __getattr__(name: str):
    if name in ("AGENTS", "get_agent", "list_by_vertical", "list_by_type"):
        from .registry import AGENTS, get_agent, list_by_vertical, list_by_type

        mapping = {
            "AGENTS": AGENTS,
            "get_agent": get_agent,
            "list_by_vertical": list_by_vertical,
            "list_by_type": list_by_type,
        }
        return mapping[name]
    if name == "AgentOrchestrator":
        from .orchestrator import AgentOrchestrator

        return AgentOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
