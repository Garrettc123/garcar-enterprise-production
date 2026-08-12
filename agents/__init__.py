"""
Garcar Enterprise — Agent Network
=================================
The living lattice of 341 specialized, autonomous, reactive, and orchestrating agents.

This package is the permanent expansion of the original deployment signal.
"""

from .registry import AGENTS, get_agent, list_by_vertical, list_by_type
from .orchestrator import AgentOrchestrator

__all__ = [
    "AGENTS",
    "get_agent",
    "list_by_vertical",
    "list_by_type",
    "AgentOrchestrator",
]
