"""Opt-in authenticated HTTP API. No external acquisition or communication side effects."""
from __future__ import annotations
import os
import secrets
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from .models import PropertyIn, EvidenceIn, UnderwritingIn, BuyerIn, DecisionIn
from .store import CaseStore, MissingCase, Conflict

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keys are mandatory for non-health traffic. Refuse exposed startup without them.
    if not os.getenv("REOS_API_KEY"):
        raise RuntimeError("Set REOS_API_KEY before starting the service")
    app.state.store = CaseStore(os.getenv("REOS_DB_PATH", "./reos.db"))
    yield

def create_app() -> FastAPI:
    allow_docs = os.getenv("REOS_ENABLE_DOCS", "0") == "1"
    app = FastAPI(title="Garcar Real Estate Intelligence OS", version="0.1.0", lifespan=lifespan,
                  docs_url="/docs" if allow_docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if allow_docs else None)

    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        expected = os.getenv("REOS_API_KEY", "")
        supplied = request.headers.get("x-api-key", "")
        if not expected or not secrets.compare_digest(supplied, expected):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    def store(req: Request) -> CaseStore:
        return req.app.state.store

    @app.exception_handler(MissingCase)
    async def missing_handler(req: Request, exc: MissingCase):
        return JSONResponse({"detail": "Case not found"}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict_handler(req: Request, exc: Conflict):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "garcar-reos", "version": "0.1.0"}

    @app.post("/v1/cases", status_code=201)
    def add_case(body: PropertyIn, s: CaseStore = Depends(store)):
        return s.add_case(body)

    @app.get("/v1/cases")
    def list_cases(limit: int = 50, s: CaseStore = Depends(store)):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "limit must be between 1 and 100")
        return s.list_cases(limit)

    @app.get("/v1/cases/{case_id}")
    def get_case(case_id: str, s: CaseStore = Depends(store)):
        return s.get_case(case_id)

    @app.post("/v1/cases/{case_id}/evidence", status_code=201)
    def add_evidence(case_id: str, body: EvidenceIn, s: CaseStore = Depends(store)):
        return s.add_evidence(case_id, body)

    @app.get("/v1/cases/{case_id}/evidence")
    def list_evidence(case_id: str, s: CaseStore = Depends(store)):
        return s.list_evidence(case_id)

    @app.post("/v1/cases/{case_id}/underwrite", status_code=201)
    def underwrite(case_id: str, body: UnderwritingIn, s: CaseStore = Depends(store)):
        return s.run_underwriting(case_id, body)

    @app.get("/v1/cases/{case_id}/underwriting/latest")
    def last_underwriting(case_id: str, s: CaseStore = Depends(store)):
        result = s.latest_underwriting(case_id)
        if result is None:
            raise HTTPException(404, "Underwriting not found")
        return result

    @app.get("/v1/cases/{case_id}/readiness")
    def readiness(case_id: str, s: CaseStore = Depends(store)):
        return s.readiness(case_id)

    @app.post("/v1/cases/{case_id}/research-decision", status_code=201)
    def research_decision(case_id: str, body: DecisionIn, req: Request, s: CaseStore = Depends(store)):
        expected = os.getenv("REOS_APPROVER_KEY", "")
        supplied = req.headers.get("x-approver-key", "")
        if not expected or not secrets.compare_digest(supplied, expected):
            raise HTTPException(403, "Approver credential required")
        return s.decide(case_id, body)

    @app.post("/v1/buyers", status_code=201)
    def add_buyer(body: BuyerIn, s: CaseStore = Depends(store)):
        return s.add_buyer(body)

    @app.get("/v1/cases/{case_id}/buyer-matches")
    def buyer_matches(case_id: str, s: CaseStore = Depends(store)):
        return s.match_buyers(case_id)

    @app.get("/v1/audit/verify")
    def verify(s: CaseStore = Depends(store)):
        return s.verify_audit()

    return app

app = create_app()
