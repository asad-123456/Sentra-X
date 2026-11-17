"""Container entrypoint: wait for Postgres, run Alembic migrations, optionally seed an empty database, start the API.

Safe to run on every start: migrations are idempotent, and demo data is loaded only when the users table is empty
and SEED_DEMO_DATA is true. Asad's migrations create the tables and the append-only audit trigger."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from app.database import sync_engine  # noqa: E402


def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            with sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("database reachable", flush=True)
            return
        except Exception as exc:  # Postgres may still be starting
            print(f"database not ready ({attempt}/{retries}): {exc.__class__.__name__}", flush=True)
            time.sleep(delay)
    raise SystemExit("database never became reachable")


def seed_if_empty() -> None:
    if os.getenv("SEED_DEMO_DATA", "true").strip().lower() not in ("1", "true", "yes"):
        return
    with sync_engine.connect() as conn:
        users = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    if users:
        print(f"users table has {users} rows, demo seed skipped", flush=True)
        return
    from app.seed_data import seed_database

    print("empty database: loading demo data", flush=True)
    if not seed_database():
        raise SystemExit("demo seed failed")


def main() -> None:
    wait_for_db()
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    seed_if_empty()
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()
