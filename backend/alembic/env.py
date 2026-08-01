"""
alembic/env.py — LiquorIQ migration environment

Two things this file does that the default env.py does NOT:
  1. Reads the DATABASE_URL from our .env file (via app.config) so secrets
     never live in alembic.ini.
  2. Runs migrations asynchronously using asyncpg — required because our
     SQLAlchemy engine is async.

Alembic calls run_migrations_online() when you run `alembic upgrade head`.
It imports Base.metadata so it knows about every table defined in our models.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Import our app's Base and settings ───────────────────────────────────────
# IMPORTANT: as we add new model files (user.py, store.py, etc.) we must
# import them here so Alembic can detect their tables for autogenerate.
from app.config import get_settings
from app.database import Base  # noqa: F401 — keeps metadata populated

# Import all models so Alembic sees their table definitions.
# Add new model imports here as we create them in later phases.
from app.models import user, store, uploaded_report, normalized_sale  # noqa: F401 — Phase 3-5
from app.models import ai_strategy_report  # noqa: F401 — Phase 7
from app.models import ad_creative  # noqa: F401 — Phase 10
from app.models import transfer  # noqa: F401 — Phase 14
from app.models import deal_buy  # noqa: F401 — Phase 15
from app.models import product_photo  # noqa: F401 — Phase 16
from app.models import customer  # noqa: F401 — Phase 19
from app.models import campaign  # noqa: F401 — Phase 21
from app.models import product_facts  # noqa: F401 — Professional Ad Upgrade
from app.models import label_design  # noqa: F401 — Label Studio

settings_app = get_settings()

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

# Wire up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at our table metadata
target_metadata = Base.metadata

# Override the DB URL from our app settings (reads from .env)
config.set_main_option("sqlalchemy.url", settings_app.database_url)


# ─── Offline migrations (rarely used — generates raw SQL without connecting) ──

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ─── Online migrations (normal usage: connects to DB and applies changes) ─────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,            # detect column type changes
        compare_server_default=True,  # detect default value changes
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pooling during migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ─── Entry point ─────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()