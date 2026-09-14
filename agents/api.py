"""FastAPI control surface for the 482-agent governed revenue fabric."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from database import get_db
from .runtime import get_runtime
from .agent_catalog import AGENT_CATALOG
from .agent_engine import AgentEngine

router=APIRouter(prefix="/api/agents",tags=["agents"])
_engine=AgentEngine(AGENT_CATALOG)

class DispatchRequest(BaseModel):
    payload:dict[str,Any]=Field(default_factory=dict)
    requested_spend_cents:int=Field(default=0,ge=0,le=1_000_000)
    human_approval:bool=False

@router.get("/status")
def agent_status(db:Session=Depends(get_db)):
    runtime=get_runtime(db_session_factory=lambda:db)
    return {"runtime":runtime.status(),"fabric":_engine.inventory()}

@router.get("/inventory")
def inventory():
    return {"source_records":497,"unique_agents":len(AGENT_CATALOG),"agents":AGENT_CATALOG}

@router.get("/{name}")
def agent_info(name:str):
    for agent in AGENT_CATALOG:
        if agent["name"]==name:return agent
    raise HTTPException(404,"agent not found")

@router.post("/activate-all")
def activate_all():
    return {"status":"all_482_agents_activated",**_engine.inventory(),"execution_policy":{"economic_objectives":"enabled","autonomous_spend_ceiling_cents":2500,"external_side_effects":"explicit_tool_only","high_risk_actions":"human_approval_required","production_merge":"human_only"}}

@router.post("/{name}/dispatch")
async def dispatch(name:str,request:DispatchRequest):
    try:return await _engine.dispatch(name,request.payload,request.requested_spend_cents,request.human_approval)
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except Exception as exc:raise HTTPException(500,str(exc)) from exc

@router.post("/run-all")
async def run_all(request:DispatchRequest):
    results=[]
    for agent in AGENT_CATALOG:
        results.append(await _engine.dispatch(agent["name"],request.payload,request.requested_spend_cents,request.human_approval))
    return {"status":"completed","count":len(results),"results":results}

@router.post("/start")
async def start_runtime(db:Session=Depends(get_db)):
    runtime=get_runtime(db_session_factory=lambda:db);await runtime.start();return {"status":"started",**runtime.status()}

@router.post("/stop")
async def stop_runtime():
    runtime=get_runtime();await runtime.stop();return {"status":"stopped"}

@router.get("/events")
def recent_events(db:Session=Depends(get_db)):
    runtime=get_runtime(db_session_factory=lambda:db);return {"events":runtime.engine.revenue_events[-50:],"total_logged":len(runtime.engine.revenue_events)}

@router.post("/force-cycle")
async def force_cycle(db:Session=Depends(get_db)):
    runtime=get_runtime(db_session_factory=lambda:db)
    if not runtime.running:await runtime.start()
    await runtime._execute_cycle()
    return {"status":"cycle_executed","cycle":runtime.total_cycles,"events":runtime.engine.revenue_events[-5:]}
