"""Alembic environment configuration for Sentra-X.

Configured for synchronous migrations using psycopg v3.
Both online and offline modes use settings.DATABASE_URL (sync URL).
"""

from __future__ import annotations

import sys
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Make the `backend/` directory importable so we can reach app.*
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import all models so Base.metadata is fully populated before any migration
# introspection happens.
from app.config import settings  # noqa: E402
from app.models import (  # noqa: E402, F401 – side-effect import to register tables
    User,
    Asset,
    Alert,
    EvidencePack,
    AIAssessment,
    AnalystDecisionAudit,
    FeedbackExemplar,
)
from app.models.base import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to alembic.ini)
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url with the value from pydantic-settings so that
# we never have to hard-code credentials inside alembic.ini.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for 'autogenerate' support.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode (generate SQL script without a live DB connection)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (run against a live DB connection)
# ---------------------------------------------------------------------------

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
