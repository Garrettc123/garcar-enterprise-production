"""Garcar Revenue Autopilot control plane.

Deterministic revenue workflow orchestration. The model/agent layer may recommend
an action, but policy gates decide whether it can execute. Financial actions and
external communications remain explicitly bounded by configured capabilities.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/autopilot", tags=["revenue-autopilot"])
DB_PATH = Path(os.getenv("AUTOPILOT_DB_PATH", "./autonomy/autopilot.sqlite3"))
ADMIN_TOKEN = os.getenv("AUTOPILOT_ADMIN_TOKEN", "")

class Stage(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    FIT_CALL = "fit_call"
    DIAGNOSTIC = "diagnostic"
    SPRINT = "sprint"
    MANAGED = "managed"
    CLOSED = "closed"

class LeadIn(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    source: str = Field(default="unknown", max_length=100)
    trigger: str | None = Field(default=None, max_length=1000)
    estimated_opportunity_value: float | None = Field(default=None, ge=0)

class ActionOut(BaseModel):
    action: str
    lead_id: int
    due_at: str
    reason: str
    requires_human_approval: bool = True


def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        contact_name TEXT,
        email TEXT,
        source TEXT NOT NULL,
        trigger TEXT,
        estimated_opportunity_value REAL,
        stage TEXT NOT NULL,
        next_action TEXT,
        next_action_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    db.commit()
    return db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _auth(token: str | None) -> None:
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Autopilot authorization required")


@router.get("/health")
def health() -> dict[str, Any]:
    db = _db()
    total = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    open_count = db.execute("SELECT COUNT(*) FROM leads WHERE stage NOT IN ('closed')").fetchone()[0]
    db.close()
    return {"status": "operational", "leads": total, "open_leads": open_count}


@router.post("/leads", response_model=ActionOut)
def ingest_lead(lead: LeadIn, x_autopilot_token: str | None = Header(default=None)) -> ActionOut:
    _auth(x_autopilot_token)
    now = _now()
    # Conservative qualification: valuable enough to justify a human fit call.
    qualified = (lead.estimated_opportunity_value or 0) >= float(os.getenv("AUTOPILOT_MIN_OPPORTUNITY", "10000"))
    stage = Stage.QUALIFIED if qualified else Stage.NEW
    action = "send_fit_call_invitation" if qualified and lead.email else "request_missing_contact_data"
    due = now + timedelta(hours=2 if qualified else 24)
    db = _db()
    cur = db.execute(
        "INSERT INTO leads(company,contact_name,email,source,trigger,estimated_opportunity_value,stage,next_action,next_action_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (lead.company, lead.contact_name, lead.email, lead.source, lead.trigger, lead.estimated_opportunity_value,
         stage.value, action, due.isoformat(), now.isoformat(), now.isoformat()),
    )
    lead_id = cur.lastrowid
    db.execute("INSERT INTO events(lead_id,event_type,payload,created_at) VALUES(?,?,?,?)",
               (lead_id, "lead_ingested", lead.model_dump_json(), now.isoformat()))
    db.commit(); db.close()
    return ActionOut(action=action, lead_id=lead_id, due_at=due.isoformat(),
                      reason="Qualified by configured opportunity threshold" if qualified else "Insufficient opportunity data",
                      requires_human_approval=True)


@router.get("/queue")
def queue(x_autopilot_token: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _auth(x_autopilot_token)
    db = _db()
    rows = db.execute("SELECT * FROM leads WHERE stage NOT IN ('closed') ORDER BY next_action_at ASC LIMIT 100").fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("/lead/{lead_id}/advance")
def advance(lead_id: int, stage: Stage, x_autopilot_token: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(x_autopilot_token)
    db = _db(); now = _now()
    row = db.execute("SELECT id FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not row:
        db.close(); raise HTTPException(status_code=404, detail="Lead not found")
    db.execute("UPDATE leads SET stage=?, updated_at=? WHERE id=?", (stage.value, now.isoformat(), lead_id))
    db.execute("INSERT INTO events(lead_id,event_type,payload,created_at) VALUES(?,?,?,?)",
               (lead_id, "stage_advanced", stage.value, now.isoformat()))
    db.commit(); db.close()
    return {"lead_id": lead_id, "stage": stage.value, "updated_at": now.isoformat()}
