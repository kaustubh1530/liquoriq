"""
main.py — LiquorIQ FastAPI application entry point

This file:
  - Creates the FastAPI app instance with lifespan (startup/shutdown)
  - Registers all routers (one per feature domain)
  - Configures CORS so the React frontend can talk to the API
  - Starts APScheduler on startup, stops it on shutdown
  - Provides /health and / root endpoints for quick verification
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


# ─── Lifespan (startup + shutdown) ───────────────────────────────────────────
# FastAPI's modern replacement for @app.on_event("startup")
# The scheduler starts here so it's alive for the entire app lifetime.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    start_scheduler()
    yield
    # ── Shutdown ──
    stop_scheduler()


# ─── App instance ────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered growth intelligence platform for independent liquor stores. "
        "Connects sales, inventory, customer, and delivery-platform data to "
        "generate analytics and AI-driven promotion strategies."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
from app.routes import auth, stores, uploads, analytics, ai, reports  # noqa: E402

app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(stores.router,    prefix="/stores",    tags=["Stores"])
app.include_router(uploads.router,   prefix="/uploads",   tags=["Uploads"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(ai.router,        prefix="/ai",        tags=["AI"])
app.include_router(reports.router,   prefix="/reports",   tags=["Reports"])


# ─── Root endpoints ───────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "environment": settings.app_env,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    db_status = "unreachable"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.app_name,
        "database": db_status,
    }
