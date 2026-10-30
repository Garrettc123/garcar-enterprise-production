import os
import hashlib
import json
import logging
from typing import TypedDict, Literal, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
import stripe
import hvac
from langgraph.graph import StateGraph, START, END

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("garcar-gateway")

def load_vault_secrets() -> Dict[str, str]:
    vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_token = os.getenv("VAULT_TOKEN", "dev-token")
    try:
        client = hvac.Client(url=vault_addr, token=vault_token)
        if client.is_authenticated():
            secret_response = client.secrets.kv.v2.read_secret_version(
                mount_point="secret",
                path="garcar/production/keys"
            )
            logger.info("Loaded secrets from HashiCorp Vault.")
            return secret_response["data"]["data"]
    except Exception as e:
        logger.warning("Vault unavailable (%s). Falling back to environment variables.", e)
    return {
        "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY", "sk_test_placeholder"),
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "mock_access_key"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "mock_secret_key"),
        "S3_LEDGER_BUCKET": os.getenv("S3_LEDGER_BUCKET", "garcar-enterprise-immutable-ledger"),
    }

SECRETS = load_vault_secrets()
stripe.api_key = SECRETS.get("STRIPE_SECRET_KEY")
S3_BUCKET_NAME = SECRETS.get("S3_LEDGER_BUCKET")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=SECRETS.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=SECRETS.get("AWS_SECRET_ACCESS_KEY"),
)

class LeadState(TypedDict, total=False):
    permit_id: str
    municipality: str
    contractor_name: str
    property_address: str
    valuation: float
    description: str
    filing_date: str
    ledger_hash: str
    graphrag_context: Dict[str, Any]
    rhns_approved: bool
    risk_score: float
    outreach_draft: str
    payment_link: str
    status: str

def ledger_lock_node(state: LeadState) -> LeadState:
    logger.info("[Ledger] Sealing permit %s", state.get("permit_id"))
    payload = {
        "permit_id": state.get("permit_id"),
        "municipality": state.get("municipality"),
        "contractor_name": state.get("contractor_name"),
        "valuation": state.get("valuation"),
        "event_type": "ORCHESTRATION_INPUT_SEALED",
    }
    content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    s3_key = f"orchestration/leads/{str(state.get('municipality','unknown')).lower()}/{state.get('permit_id')}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps({**payload, "sha256_hash": content_hash}, indent=2),
            ContentType="application/json",
        )
        state["ledger_hash"] = content_hash
        state["status"] = "LEDGER_LOCKED"
    except Exception as e:
        logger.error("Ledger write failed: %s", e)
        state["status"] = f"LEDGER_FAILED: {e}"
    return state

def graphrag_enrich_node(state: LeadState) -> LeadState:
    logger.info("[GraphRAG] Enriching %s", state.get("permit_id"))
    state["graphrag_context"] = {
        "contractor_rating": 4.9,
        "past_projects_count": 22,
        "market_segment": "Commercial Industrial DFW",
        "trades": ["HVAC", "Roofing", "Plumbing"],
    }
    state["status"] = "GRAPHRAG_ENRICHED"
    return state

def rhns_guardrail_node(state: LeadState) -> LeadState:
    logger.info("[RHNS] Evaluating %s", state.get("permit_id"))
    valuation = float(state.get("valuation") or 0)
    rating = float(state.get("graphrag_context", {}).get("contractor_rating", 0))
    if valuation < 75000 and rating >= 4.0:
        state["rhns_approved"] = True
        state["risk_score"] = 0.08
        state["status"] = "RHNS_AUTO_APPROVED"
    else:
        state["rhns_approved"] = False
        state["risk_score"] = 0.91
        state["status"] = "RHNS_REQUIRES_HUMAN_REVIEW"
    return state

def outreach_generation_node(state: LeadState) -> LeadState:
    logger.info("[Outreach] Drafting for %s", state.get("contractor_name"))
    payment_link = "https://buy.stripe.com/3cI00j7YV0hQgDp8BR43S2v"
    state["payment_link"] = payment_link
    name = state.get("contractor_name") or "there"
    address = state.get("property_address") or "your project"
    val = state.get("valuation") or 0
    state["outreach_draft"] = (
        f"Hey {name} — Garrett in Grandview. "
        f"Your permit at {address} (${val:,.0f}) just hit the system. "
        f"I map the first-response gap where Texas HVAC/roofing/plumbing shops lose the job after the lead lands. "
        f"$47, delivered to your email. If the map is wrong you say so. "
        f"Pay: {payment_link}"
    )
    state["status"] = "OUTREACH_READY"
    return state

def route_after_guardrails(state: LeadState) -> Literal["outreach_gen", "end"]:
    return "outreach_gen" if state.get("rhns_approved") else "end"

def build_lead_orchestrator():
    workflow = StateGraph(LeadState)
    workflow.add_node("ledger_lock", ledger_lock_node)
    workflow.add_node("graphrag_enrich", graphrag_enrich_node)
    workflow.add_node("rhns_guardrails", rhns_guardrail_node)
    workflow.add_node("outreach_gen", outreach_generation_node)
    workflow.add_edge(START, "ledger_lock")
    workflow.add_edge("ledger_lock", "graphrag_enrich")
    workflow.add_edge("graphrag_enrich", "rhns_guardrails")
    workflow.add_conditional_edges(
        "rhns_guardrails",
        route_after_guardrails,
        {"outreach_gen": "outreach_gen", "end": END},
    )
    workflow.add_edge("outreach_gen", END)
    return workflow.compile()

compiled_graph = build_lead_orchestrator()

app = FastAPI(title="Garcar Enterprise Zero-Human Autonomous Wealth Engine")

class PermitPayload(BaseModel):
    permit_id: str
    municipality: str
    contractor_name: str
    property_address: str
    valuation: float
    description: str
    filing_date: str

@app.get("/health")
async def health():
    return {"status": "ok", "service": "garcar-gateway", "ledger_bucket": S3_BUCKET_NAME}

@app.post("/webhook/permits/dfw")
async def ingest_permit(permit: PermitPayload):
    initial_state: LeadState = {
        **permit.model_dump(),
        "ledger_hash": "",
        "graphrag_context": {},
        "rhns_approved": False,
        "risk_score": 0.0,
        "outreach_draft": "",
        "payment_link": "",
        "status": "INITIALIZED",
    }
    try:
        final_state = compiled_graph.invoke(initial_state)
        return {
            "status": "success",
            "execution_status": final_state.get("status"),
            "ledger_hash": final_state.get("ledger_hash"),
            "rhns_approved": final_state.get("rhns_approved"),
            "outreach_draft": final_state.get("outreach_draft"),
            "payment_link": final_state.get("payment_link"),
        }
    except Exception as e:
        logger.exception("Orchestrator failed")
        raise HTTPException(status_code=500, detail=str(e))
