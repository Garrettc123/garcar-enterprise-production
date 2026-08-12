"""
GARCAR Enterprise Platform — Production API
=============================================
FastAPI backend with auth, Stripe payments, product APIs, lead capture,
admin dashboard, Money Flow Loop, and the LIVE Autonomous Agent Runtime.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("garcar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown — agents boot with the platform."""
    from database import init_db, SessionLocal

    logger.info("Initializing database...")
    init_db()

    # ── BOOT THE AUTONOMOUS REVENUE ORGANISM ──────────────────────────────
    try:
        from agents.runtime import get_runtime
        runtime = get_runtime(db_session_factory=SessionLocal)
        await runtime.start()
        logger.info("AUTONOMOUS AGENT RUNTIME STARTED — revenue agents are live")
    except Exception as e:
        logger.error(f"Failed to start agent runtime (platform still up): {e}")

    logger.info("GARCAR Platform API started")
    yield

    # Shutdown
    try:
        from agents.runtime import get_runtime
        runtime = get_runtime()
        await runtime.stop()
    except Exception:
        pass
    logger.info("Shutting down")


app = FastAPI(
    title="GARCAR Enterprise Platform",
    description="AI-powered business automation — Deal Desk, SEO Factory, Churn Predictor + Live Agent Revenue Engine",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow frontend origins
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permissive for development; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount all routers ---
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

# Money Flow Loop
try:
    from money_flow_loop.api import router as money_flow_router
    app.include_router(money_flow_router)
except Exception as e:
    logger.warning(f"Money Flow Loop not mounted: {e}")

# Autonomous Agent Network
try:
    from agents.api import router as agents_router
    app.include_router(agents_router)
except Exception as e:
    logger.warning(f"Agent API not mounted: {e}")


# --- Root & Health ---
@app.get("/")
def root():
    return {
        "name": "GARCAR Enterprise Platform",
        "version": "1.1.0",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "auth": "/api/auth",
            "payments": "/api/payments",
            "products": "/api/products",
            "leads": "/api/leads",
            "admin": "/api/admin",
            "nurture": "/api/nurture",
            "webhooks": "/api/webhooks/stripe",
            "money_flow": "/api/money-flow",
            "agents": "/api/agents",
        },
        "agents": "Autonomous revenue runtime boots with the platform",
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
        "agents": {
            "running": agent_status.get("running", False),
            "cycles": agent_status.get("total_cycles", 0),
        },
    }


# --- Error handlers ---
@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found", "docs": "/docs"})


@app.exception_handler(500)
async def server_error(request, exc):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
