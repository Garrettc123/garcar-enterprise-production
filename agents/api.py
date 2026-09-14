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
from .revenue_adapters import RevenueAdapters
from .revenue_missions import build_missions

router=APIRouter(prefix="/api/agents",tags=["agents"])
_engine=AgentEngine(AGENT_CATALOG)

class DispatchRequest(BaseModel):
    payload:dict[str,Any]=Field(default_factory=dict)
    requested_spend_cents:int=Field(default=0,ge=0,le=1_000_000)
    human_approval:bool=False

def _wire(db:Session):
    runtime=get_runtime(db_session_factory=lambda:db)
    runtime.engine.db_session_factory=lambda:db
    adapters=RevenueAdapters(runtime.engine)
    for name,fn in adapters.registry().items(): _engine.register_tool(name,fn)
    return runtime

@router.get("/status")
def agent_status(db:Session=Depends(get_db)):
    runtime=_wire(db)
    return {"runtime":runtime.status(),"fabric":_engine.inventory(),"revenue_missions":build_missions()}

@router.get("/inventory")
def inventory():
    return {"source_records":497,"unique_agents":len(AGENT_CATALOG),"agents":AGENT_CATALOG}

@router.get("/revenue/missions")
def revenue_missions():
    return {"objective":"maximize verified revenue","missions":build_missions()}

@router.get("/{name}")
def agent_info(name:str):
    for agent in AGENT_CATALOG:
        if agent["name"]==name:return agent
    raise HTTPException(404,"agent not found")

@router.post("/activate-all")
def activate_all(db:Session=Depends(get_db)):
    _wire(db)
    return {"status":"all_482_agents_activated",**_engine.inventory(),"execution_policy":{"economic_objectives":"enabled","autonomous_spend_ceiling_cents":2500,"external_side_effects":"explicit_tool_only","high_risk_actions":"human_approval_required","production_merge":"human_only"}}

@router.post("/{name}/dispatch")
async def dispatch(name:str,request:DispatchRequest,db:Session=Depends(get_db)):
    _wire(db)
    try:return await _engine.dispatch(name,request.payload,request.requested_spend_cents,request.human_approval)
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except Exception as exc:raise HTTPException(500,str(exc)) from exc

@router.post("/run-all")
async def run_all(request:DispatchRequest,db:Session=Depends(get_db)):
    _wire(db)
    results=[]
    for agent in AGENT_CATALOG:
        results.append(await _engine.dispatch(agent["name"],request.payload,request.requested_spend_cents,request.human_approval))
    return {"status":"completed","count":len(results),"results":results}

@router.post("/run-revenue-cycle")
async def run_revenue_cycle(db:Session=Depends(get_db)):
    runtime=_wire(db)
    if not runtime.running: await runtime.start()
    await runtime._execute_cycle()
    return {"status":"revenue_cycle_executed","cycle":runtime.total_cycles,"verified_events":runtime.engine.revenue_events[-10:],"revenue_status":runtime.engine.get_stats()}

@router.post("/start")
async def start_runtime(db:Session=Depends(get_db)):
    runtime=_wire(db);await runtime.start();return {"status":"started",**runtime.status(),"fabric":_engine.inventory()}

@router.post("/stop")
async def stop_runtime():
    runtime=get_runtime();await runtime.stop();return {"status":"stopped"}

@router.get("/events")
def recent_events(db:Session=Depends(get_db)):
    runtime=_wire(db);return {"events":runtime.engine.revenue_events[-50:],"total_logged":len(runtime.engine.revenue_events)}

@router.post("/force-cycle")
async def force_cycle(db:Session=Depends(get_db)):
    runtime=_wire(db)
    if not runtime.running:await runtime.start()
    await runtime._execute_cycle()
    return {"status":"cycle_executed","cycle":runtime.total_cycles,"events":runtime.engine.revenue_events[-5:]}
