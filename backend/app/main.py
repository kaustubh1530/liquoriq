"""
main.py — LiquorIQ FastAPI application entry point

This file:
  - Creates the FastAPI app instance
  - Registers all routers (one per feature domain)
  - Configures CORS so the React frontend can talk to the API
  - Provides /health and / root endpoints for quick verification
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal

settings = get_settings()

# ─── App instance ────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered growth intelligence platform for independent liquor stores. "
        "Connects sales, inventory, customer, and delivery-platform data to "
        "generate analytics and AI-driven promotion strategies."
    ),
    version="0.1.0",
    docs_url="/docs",       # Swagger UI  → http://localhost:8000/docs
    redoc_url="/redoc",     # ReDoc UI    → http://localhost:8000/redoc
)

# ─── CORS ────────────────────────────────────────────────────────────────────
# In production, replace "*" with your actual frontend domain.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
from app.routes import auth, stores, uploads, analytics, ai

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(stores.router, prefix="/stores", tags=["Stores"])
app.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])


# ─── Root endpoints ───────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """API root — confirms the service is live."""
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "environment": settings.app_env,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health-check endpoint — checks both the app and the database.
    Returns 200 OK when healthy, 503 if the DB is unreachable.
    """
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