"""
GARCAR Enterprise Platform — Production API
=============================================
FastAPI backend with auth, Stripe payments, product APIs, lead capture, and admin dashboard.
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
    """Startup and shutdown."""
    from database import init_db

    logger.info("Initializing database...")
    init_db()
    logger.info("GARCAR Platform API started")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="GARCAR Enterprise Platform",
    description="AI-powered business automation — Deal Desk, SEO Factory, Churn Predictor",
    version="1.0.0",
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


# --- Root & Health ---
@app.get("/")
def root():
    return {
        "name": "GARCAR Enterprise Platform",
        "version": "1.0.0",
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
        },
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "time": datetime.now(timezone.utc).isoformat(),
        "stripe": "configured" if os.getenv("STRIPE_SECRET_KEY") else "not configured",
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
