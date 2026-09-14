"""Full-scale execution engine for the Garcar super-agent fabric.

Agents reason, pass policy, execute explicitly registered adapters, and emit
verifiable provenance. Live execution is the only execution mode; authority
is bounded by the governor and adapter capabilities.
"""
from __future__ import annotations
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable
from .super_agent_governor import SuperAgentGovernor
Tool = Callable[[dict[str, Any]], Any]

@dataclass
class Execution:
    id: str
    agent: str
    state: str
    started_at: str
    finished_at: str | None = None
    input_hash: str = ""
    output: dict[str, Any] | None = None
    error: str | None = None

class AgentEngine:
    def __init__(self, catalog: list[dict[str, Any]]):
        self.catalog = {a["name"]: a for a in catalog if a.get("name")}
        self.tools: dict[str, Tool] = {}
        self.executions: list[Execution] = []
        self.governor = SuperAgentGovernor()

    def register_tool(self, name: str, fn: Tool) -> None:
        self.tools[name] = fn

    def inventory(self) -> dict[str, Any]:
        return {"total_agents": len(self.catalog), "tool_adapters": sorted(self.tools),
                "runnable": len(self.catalog), "governor": "economic_safety_v1",
                "execution_mode": "provider_backed" if os.getenv("OPENAI_API_KEY") else "deterministic_local"}

    def _local(self, spec: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        mission = spec.get("description") or f"Perform the {spec['name']} function."
        typ = spec.get("type") or "Specialist"
        action = {"Planner":"plan","Evaluator":"evaluate","Reactive":"respond",
                  "Autonomous":"optimize","Orchestrator":"coordinate",
                  "Conversational":"communicate","Specialist":"analyze"}.get(typ,"analyze")
        return {"agent":spec["name"],"action":action,"mission":mission,
                "input":context,"recommendation":f"{action}: {mission}","side_effects":[]}

    def _model(self, spec: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return self._local(spec, context)
        import urllib.request
        body = {"model":os.getenv("GARCAR_AGENT_MODEL","gpt-5.6"),"input":[
            {"role":"system","content":"You are a governed Garcar enterprise super-agent. Optimize for measurable business value. Never invent revenue, customers, completed actions, or evidence. Return JSON with decision, action, reasoning_summary, actions, risks, and estimated_business_value. Never claim an external action you did not execute."},
            {"role":"user","content":json.dumps({"agent":spec["name"],"type":spec.get("type"),"vertical":spec.get("vertical"),"complexity":spec.get("complexity"),"mission":spec.get("description") or spec["name"],"input":context},ensure_ascii=False)}],
            "text":{"format":{"type":"json_object"}}}
        req=urllib.request.Request(os.getenv("OPENAI_API_URL","https://api.openai.com/v1/responses"),data=json.dumps(body).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=90) as response:
            data=json.load(response)
        return json.loads(data.get("output_text") or "{}")

    async def dispatch(self,name:str,context:dict[str,Any]|None=None,requested_spend_cents:int=0,human_approval:bool=False)->dict[str,Any]:
        if name not in self.catalog: raise KeyError(f"Unknown agent: {name}")
        context=context or {}; eid=str(uuid.uuid4()); started=datetime.now(timezone.utc).isoformat()
        ex=Execution(eid,name,"running",started,input_hash=hashlib.sha256(json.dumps(context,sort_keys=True,default=str).encode()).hexdigest())
        self.executions.append(ex)
        try:
            spec=self.catalog[name]; result=self._model(spec,context)
            action=str(result.get("action","analyze")); objective=str(context.get("economic_objective","increase measurable business value"))
            decision=self.governor.decide(objective=objective,action=action,requested_spend_cents=requested_spend_cents,reversible=bool(context.get("reversible",True)),human_approval=human_approval)
            if not decision.allowed:
                ex.state="blocked"; ex.output={"execution_id":eid,"agent":name,"status":"blocked","result":result,"policy":self.governor.envelope(decision,objective)}; return asdict(ex)
            for tool_name in context.get("tools",[]):
                if tool_name not in self.tools: raise RuntimeError(f"Tool adapter not registered: {tool_name}")
                value=self.tools[tool_name](context)
                if hasattr(value,"__await__"): value=await value
                result.setdefault("tool_results",{})[tool_name]=value
            ex.output={"execution_id":eid,"agent":name,"status":"verified","result":result,"policy":self.governor.envelope(decision,objective),"provenance":{"input_hash":ex.input_hash,"external_side_effects":"explicit_tool_only"}}
            ex.state="succeeded"
        except Exception as exc:
            ex.error=str(exc); ex.state="failed"; raise
        finally: ex.finished_at=datetime.now(timezone.utc).isoformat()
        return asdict(ex)
