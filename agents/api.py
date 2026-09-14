"""FastAPI control surface for the GARCAR agent lattice."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from .runtime import get_runtime
from .orchestrator import AgentOrchestrator

router = APIRouter(prefix="/api/agents", tags=["agents"])


class DispatchRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def agent_status(db: Session = Depends(get_db)):
    runtime = get_runtime(db_session_factory=lambda: db)
    return runtime.status()


@router.get("/inventory")
def inventory():
    """Return the complete deduplicated ExportBlock agent inventory."""
    control = AgentOrchestrator().control
    return {"source_records": 497, "unique_agents": len(control.agents), "agents": control.agents}


@router.post("/activate-all")
def activate_all():
    """Activate every registered capability identity; does not grant side-effect permissions."""
    return AgentOrchestrator().deploy_all()


@router.post("/{name}/dispatch")
def dispatch(name: str, request: DispatchRequest):
    """Dispatch work to an agent. Without an installed adapter this is capability-only."""
    try:
        return AgentOrchestrator().dispatch(name, request.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/start")
async def start_runtime(db: Session = Depends(get_db)):
    runtime = get_runtime(db_session_factory=lambda: db)
    await runtime.start()
    return {"status": "started", **runtime.status()}


@router.post("/stop")
async def stop_runtime():
    runtime = get_runtime()
    await runtime.stop()
    return {"status": "stopped"}


@router.get("/events")
def recent_events(db: Session = Depends(get_db)):
    runtime = get_runtime(db_session_factory=lambda: db)
    return {"events": runtime.engine.revenue_events[-50:], "total_logged": len(runtime.engine.revenue_events)}


@router.post("/force-cycle")
async def force_cycle(db: Session = Depends(get_db)):
    runtime = get_runtime(db_session_factory=lambda: db)
    if not runtime.running:
        await runtime.start()
    await runtime._execute_cycle()
    return {"status": "cycle_executed", "cycle": runtime.total_cycles, "events": runtime.engine.revenue_events[-5:]}
