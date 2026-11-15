from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

# ---------------------------------------------------------------------------
# Sync engine – used by the Wazuh ingest worker / triage pipeline
# ---------------------------------------------------------------------------
sync_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

# ---------------------------------------------------------------------------
# Async engine – used by FastAPI web routes
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency helpers
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """Sync DB session dependency for FastAPI (or background workers)."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async DB session dependency for FastAPI route handlers."""
    async with AsyncSessionLocal() as session:
        yield session
