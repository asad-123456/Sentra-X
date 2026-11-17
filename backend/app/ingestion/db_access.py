"""Thin bridge to Asad's database module (app/database.py).

Ingestion uses his synchronous session factory. Keeping this one function means
the poller, webhook and replay tool never import database.py directly, and the
tests can swap the factory through FastAPI's dependency_overrides."""
from sqlalchemy.orm import sessionmaker

from app.database import SyncSessionLocal


def get_session_factory() -> sessionmaker:
    return SyncSessionLocal
