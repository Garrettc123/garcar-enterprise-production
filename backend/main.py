"""
GARCAR Enterprise Platform — Production API
=============================================
FastAPI backend with auth, Stripe payments, lead capture, Money Flow Loop,
and guarded autonomous revenue orchestration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("garcar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db, SessionLocal
    logger.info("Initializing database...")
    init_db()
    try:
        from agents.runtime import get_runtime
        runtime = get_runtime(db_session_factory=SessionLocal)
        await runtime.start()
        logger.info("AUTONOMOUS AGENT RUNTIME STARTED")
    except Exception as e:
        logger.error(f"Agent runtime unavailable: {e}")
    yield
    try:
        from agents.runtime import get_runtime
        await get_runtime().stop()
    except Exception:
        pass


app = FastAPI(
    title="GARCAR Enterprise Platform",
    description="Revenue operations, payments, workflow automation and guarded agent runtime",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from auth import router as auth_router
from payments import router as payments_router, webhook_router
from leads import router as leads_router
from products import router as products_router
from admin import router as admin_router
from nurture import router as nurture_router

app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(webhook_router)
app.include_router(leads_router)
app.include_router(products_router)
app.include_router(admin_router)
app.include_router(nurture_router)

try:
    from money_flow_loop.api import router as money_flow_router
    app.include_router(money_flow_router)
except Exception as e:
    logger.warning(f"Money Flow Loop not mounted: {e}")

try:
    from agents.api import router as agents_router
    app.include_router(agents_router)
except Exception as e:
    logger.warning(f"Agent API not mounted: {e}")

try:
    from autonomy.revenue_autopilot import router as autopilot_router
    app.include_router(autopilot_router)
except Exception as e:
    logger.warning(f"Revenue Autopilot not mounted: {e}")


@app.get("/")
def root():
    return {
        "name": "GARCAR Enterprise Platform",
        "version": "1.2.0",
        "status": "operational",
        "revenue_surface": "https://garrettc123.github.io/",
        "endpoints": {
            "payments": "/api/payments",
            "leads": "/api/leads",
            "money_flow": "/api/money-flow",
            "agents": "/api/agents",
            "autopilot": "/api/autopilot",
        },
    }


@app.get("/health")
def health():
    agent_status = {}
    try:
        from agents.runtime import get_runtime
        agent_status = get_runtime().status()
    except Exception:
        agent_status = {"running": False}
    return {
        "status": "healthy",
        "time": datetime.now(timezone.utc).isoformat(),
        "stripe": "configured" if os.getenv("STRIPE_SECRET_KEY") else "not configured",
        "agents": {"running": agent_status.get("running", False), "cycles": agent_status.get("total_cycles", 0)},
    }


@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found", "docs": "/docs"})


@app.exception_handler(500)
async def server_error(request, exc):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
