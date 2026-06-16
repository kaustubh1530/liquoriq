"""
database.py — LiquorIQ async database layer

Three things live here:
  1. engine       — the single async connection pool to PostgreSQL
  2. AsyncSession — a factory for database sessions (one per request)
  3. Base         — the declarative base that all ORM models inherit from

Why async?
  FastAPI is an async framework. Using an async database driver (asyncpg)
  means database queries don't block the event loop — the server can handle
  other requests while waiting for a DB response. This is critical for a
  SaaS product under real load.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ─── Engine ──────────────────────────────────────────────────────────────────
# The engine manages the connection pool to PostgreSQL.
# pool_pre_ping=True: tests connections before using them, auto-reconnects
# if the DB was restarted.
# echo=True in dev: logs every SQL query to the console (turn off in prod).

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,        # SQL logging: on in dev, off in prod
    pool_pre_ping=True,
    pool_size=10,               # max persistent connections
    max_overflow=20,            # additional connections allowed under burst
)

# ─── Session factory ──────────────────────────────────────────────────────────
# AsyncSessionLocal creates new AsyncSession instances.
# expire_on_commit=False: keeps ORM objects readable after commit without
# triggering extra DB queries — important in async context.

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─── Declarative Base ─────────────────────────────────────────────────────────
# Every ORM model (User, Store, SalesTransaction, etc.) will inherit from Base.
# SQLAlchemy uses Base.metadata to track all table definitions for Alembic.

class Base(DeclarativeBase):
    pass


# ─── Session dependency ───────────────────────────────────────────────────────
# This is a FastAPI dependency injected into route handlers.
# Usage in a route:
#
#   async def my_route(db: AsyncSession = Depends(get_db)):
#       result = await db.execute(select(User))
#
# The `async with` block guarantees the session is always closed after the
# request — even if an exception is raised.

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()