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

from app.config import get_settings

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
# We'll register routes here as we build each phase.
# Example (Phase 3):
#   from app.routes import auth, stores
#   app.include_router(auth.router, prefix="/auth", tags=["Auth"])
#   app.include_router(stores.router, prefix="/stores", tags=["Stores"])


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
    Health-check endpoint.
    Load balancers and monitoring tools hit this to verify the app is up.
    Returns 200 OK when the server is healthy.
    """
    return {"status": "healthy", "service": settings.app_name}