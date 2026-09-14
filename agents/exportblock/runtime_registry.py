"""Normalized ExportBlock registry loader.

The checked-in agent-names file is the source inventory. Duplicate names are
collapsed deterministically so dispatch has one canonical identity per name.
"""
from __future__ import annotations

from pathlib import Path

NAMES_FILE = Path(__file__).with_name("agent-names.txt")


def load_names() -> list[str]:
    text = NAMES_FILE.read_text(encoding="utf-8")
    names = []
    seen = set()
    for raw in text.splitlines():
        name = raw.strip()
        if not name or name.startswith("{") or name.startswith('"content"'):
            continue
        if name.endswith('"'):
            name = name[:-1]
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


EXPORTBLOCK_AGENTS = load_names()
