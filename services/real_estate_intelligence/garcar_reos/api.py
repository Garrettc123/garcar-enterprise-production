"""Private authenticated REOS API; inbound webhooks independently authenticated."""
from __future__ import annotations
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .models import PropertyIn, EvidenceIn, UnderwritingIn, BuyerIn, DecisionIn
from .operations import PhaseChange, ChecklistUpdate, TaskIn, TaskUpdate, AgentProposal, ProposalDecision, DraftIn, HIGH_RISK
from .platform import PlatformStore
from .store import MissingCase, Conflict
from .sources import list_sources
from .revenue import validate_signature, MAX_BODY_BYTES

@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.getenv("REOS_API_KEY", "")
    if len(key) < 24:
        raise RuntimeError("REOS_API_KEY must be at least 24 characters before starting the service")
    app.state.store = PlatformStore(os.getenv("REOS_DB_PATH", "./reos.db"))
    yield

STATIC = Path(__file__).resolve().parent / "static"

def create_app() -> FastAPI:
    docs = os.getenv("REOS_ENABLE_DOCS", "0") == "1"
    app = FastAPI(title="Garcar Real Estate Intelligence OS", version="0.2.0", lifespan=lifespan,
                  docs_url="/docs" if docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if docs else None)
    app.mount("/assets", StaticFiles(directory=str(STATIC)), name="assets")

    @app.middleware("http")
    async def security_and_auth(request: Request, call_next):
        path = request.url.path
        public = path == "/health" or path == "/dashboard" or path.startswith("/assets/")
        webhook = path == "/integrations/stripe/webhook"
        if not public and not webhook:
            expected = os.getenv("REOS_API_KEY", "")
            supplied = request.headers.get("x-api-key", "")
            if not expected or not secrets.compare_digest(supplied, expected):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = ("default-src 'none'; img-src 'self' data:; "
                                                      "script-src 'self'; style-src 'self'; "
                                                      "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        return response

    def store(req: Request) -> PlatformStore:
        return req.app.state.store

    def require_approver(req: Request) -> None:
        expected = os.getenv("REOS_APPROVER_KEY", "")
        supplied = req.headers.get("x-approver-key", "")
        if len(expected) < 24 or not secrets.compare_digest(supplied, expected):
            raise HTTPException(403, "Independent approver credential required")

    @app.exception_handler(MissingCase)
    async def missing_handler(req: Request, exc: MissingCase):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict_handler(req: Request, exc: Conflict):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "garcar-reos", "version": "0.2.0"}

    @app.get("/dashboard", include_in_schema=False)
    def dashboard():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/v1/sources")
    def sources(region: str | None = None):
        return list_sources(region)

    @app.post("/v1/cases", status_code=201)
    def add_case(body: PropertyIn, s: PlatformStore = Depends(store)):
        return s.add_case(body)

    @app.get("/v1/cases")
    def list_cases(limit: int = 50, s: PlatformStore = Depends(store)):
        if not 1 <= limit <= 100: raise HTTPException(422, "limit must be between 1 and 100")
        return s.list_cases(limit)

    @app.get("/v1/cases/{case_id}")
    def get_case(case_id: str, s: PlatformStore = Depends(store)):
        return s.get_case(case_id)

    @app.get("/v1/cases/{case_id}/dossier")
    def dossier(case_id: str, s: PlatformStore = Depends(store)):
        return s.dossier(case_id)

    @app.post("/v1/cases/{case_id}/evidence", status_code=201)
    def add_evidence(case_id: str, body: EvidenceIn, s: PlatformStore = Depends(store)):
        return s.add_evidence(case_id, body)

    @app.get("/v1/cases/{case_id}/evidence")
    def evidence(case_id: str, s: PlatformStore = Depends(store)):
        return s.list_evidence(case_id)

    @app.post("/v1/cases/{case_id}/underwrite", status_code=201)
    def underwrite(case_id: str, body: UnderwritingIn, s: PlatformStore = Depends(store)):
        return s.run_underwriting(case_id, body)

    @app.get("/v1/cases/{case_id}/underwriting/latest")
    def underwriting(case_id: str, s: PlatformStore = Depends(store)):
        result = s.latest_underwriting(case_id)
        if result is None: raise HTTPException(404, "Underwriting not found")
        return result

    @app.get("/v1/cases/{case_id}/readiness")
    def readiness(case_id: str, s: PlatformStore = Depends(store)):
        return s.readiness(case_id)

    @app.post("/v1/cases/{case_id}/research-decision", status_code=201)
    def research_decision(case_id: str, body: DecisionIn, req: Request, s: PlatformStore = Depends(store)):
        require_approver(req)
        return s.decide(case_id, body)

    @app.get("/v1/cases/{case_id}/phase")
    def phase(case_id: str, s: PlatformStore = Depends(store)):
        return s.phase(case_id)

    @app.post("/v1/cases/{case_id}/phase")
    def transition(case_id: str, body: PhaseChange, req: Request, s: PlatformStore = Depends(store)):
        if body.target in HIGH_RISK:
            require_approver(req)
        return s.change_phase(case_id, body, approved=body.target in HIGH_RISK)

    @app.get("/v1/cases/{case_id}/checklist")
    def checklist(case_id: str, s: PlatformStore = Depends(store)):
        return s.get_checklist(case_id)

    @app.put("/v1/cases/{case_id}/checklist")
    def update_checklist(case_id: str, body: ChecklistUpdate, s: PlatformStore = Depends(store)):
        return s.update_check(case_id, body)

    @app.post("/v1/cases/{case_id}/tasks", status_code=201)
    def add_task(case_id: str, body: TaskIn, s: PlatformStore = Depends(store)):
        return s.add_task(case_id, body)

    @app.get("/v1/cases/{case_id}/tasks")
    def case_tasks(case_id: str, s: PlatformStore = Depends(store)):
        return s.list_tasks(case_id)

    @app.get("/v1/tasks/due")
    def due_tasks(s: PlatformStore = Depends(store)):
        return s.list_tasks(due_only=True)

    @app.patch("/v1/tasks/{task_id}")
    def update_task(task_id: str, body: TaskUpdate, s: PlatformStore = Depends(store)):
        return s.update_task(task_id, body)

    @app.post("/v1/cases/{case_id}/drafts", status_code=201)
    def create_draft(case_id: str, body: DraftIn, s: PlatformStore = Depends(store)):
        return s.create_draft(case_id, body)

    @app.get("/v1/cases/{case_id}/drafts")
    def drafts(case_id: str, s: PlatformStore = Depends(store)):
        return s.list_drafts(case_id)

    @app.post("/v1/agent-proposals", status_code=202)
    def agent_proposal(body: AgentProposal, req: Request, s: PlatformStore = Depends(store)):
        expected = os.getenv("REOS_AGENT_KEY", "")
        supplied = req.headers.get("x-agent-key", "")
        if len(expected) < 24 or not secrets.compare_digest(expected, supplied):
            raise HTTPException(403, "Separate agent credential required")
        return s.submit_proposal(body)

    @app.get("/v1/agent-proposals")
    def agent_proposals(status: str | None = None, s: PlatformStore = Depends(store)):
        if status not in (None, "pending", "accepted", "rejected"):
            raise HTTPException(422, "Invalid proposal status")
        return s.list_proposals(status)

    @app.post("/v1/agent-proposals/{proposal_id}/decision")
    def review_proposal(proposal_id: str, body: ProposalDecision, req: Request, s: PlatformStore = Depends(store)):
        require_approver(req)
        return s.resolve_proposal(proposal_id, body)

    @app.post("/v1/buyers", status_code=201)
    def add_buyer(body: BuyerIn, s: PlatformStore = Depends(store)):
        return s.add_buyer(body)

    @app.get("/v1/cases/{case_id}/buyer-matches")
    def buyer_matches(case_id: str, s: PlatformStore = Depends(store)):
        return s.match_buyers(case_id)

    @app.get("/v1/portfolio")
    def portfolio(s: PlatformStore = Depends(store)):
        return s.metrics()

    @app.get("/v1/revenue/summary")
    def revenue(s: PlatformStore = Depends(store)):
        return s.revenue_summary()

    @app.post("/integrations/stripe/webhook", include_in_schema=False)
    async def stripe_webhook(req: Request, s: PlatformStore = Depends(store)):
        if req.headers.get("content-length", "").isdigit() and int(req.headers["content-length"]) > MAX_BODY_BYTES:
            raise HTTPException(413, "Payload too large")
        body = await req.body()
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(413, "Payload too large")
        try:
            validate_signature(body, req.headers.get("stripe-signature", ""),
                               os.getenv("REOS_STRIPE_WEBHOOK_SECRET", ""))
            event = json.loads(body)
            if not isinstance(event, dict): raise ValueError("Not a Stripe event")
            return s.ingest_event(event)
        except (ValueError, json.JSONDecodeError) as exc:
            # Do not echo signatures or request bodies into HTTP responses.
            raise HTTPException(400, "Invalid signed Stripe webhook") from exc

    @app.get("/v1/audit/verify")
    def audit(s: PlatformStore = Depends(store)):
        return s.verify_audit()

    return app

app = create_app()
