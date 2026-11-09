from __future__ import annotations

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from app.config import settings
from app.database import sync_engine

TABLES_IN_TRUNCATE_ORDER = [
    "system_configurations",
    "analyst_decisions_audit",
    "feedback_exemplars",
    "ai_assessments",
    "evidence_packs",
    "alerts",
    "assets",
    "users",
]


def _assert_safe_dev_environment() -> None:
    """Enforces that destructive wipes only run on local demonstration / test databases."""
    if not getattr(settings, "DEMO_MODE", False):
        raise RuntimeError(
            "CRITICAL SAFEGUARD: Database wipe refused. DEMO_MODE is not True in application settings."
        )

    host = sync_engine.url.host
    safe_hosts = ("localhost", "127.0.0.1", "::1", None)
    if host not in safe_hosts and not (host and host.endswith(".internal")):
        raise RuntimeError(
            f"CRITICAL SAFEGUARD: Database wipe refused. Host {host!r} is not an authorized local dev host."
        )

    db_name = sync_engine.url.database
    safe_dbs = ("sentrax", "sentrax_db", "test_db", "sentrax_test")
    if db_name not in safe_dbs:
        raise RuntimeError(
            f"CRITICAL SAFEGUARD: Database wipe refused. Target database {db_name!r} is not an authorized dev database."
        )


def wipe_database(verbose: bool = True) -> bool:
    """Safely wipes all mock/telemetry data from PostgreSQL.
    
    Uses TRUNCATE ... RESTART IDENTITY CASCADE:
    - Bypasses the row-level trg_audit_immutability trigger on analyst_decisions_audit.
    - Resets serial identity sequences (e.g. feedback_exemplars.id).
    - Preserves all tables, constraints, indexes, triggers, and Alembic version history.
    """
    _assert_safe_dev_environment()
    if verbose:
        print("=" * 70)
        print("SENTRA-X DATABASE PURGE: WIPING ALL TELEMETRY & AUDIT DATA")
        print("=" * 70)

    truncate_sql = f"TRUNCATE TABLE {', '.join(TABLES_IN_TRUNCATE_ORDER)} RESTART IDENTITY CASCADE;"

    counts = {}
    with sync_engine.begin() as conn:
        conn.execute(text(truncate_sql))
        
        # Verify counts
        for table in TABLES_IN_TRUNCATE_ORDER:
            c = conn.execute(text(f"SELECT count(*) FROM {table};")).scalar()
            counts[table] = c

    all_empty = all(count == 0 for count in counts.values())

    if verbose:
        print("\nVerification of Table Rows Post-Wipe:")
        for table, count in counts.items():
            status = "✅ Empty" if count == 0 else f"❌ {count} rows left"
            print(f"  • {table:<25} : {status}")

        print("\n" + "=" * 70)
        if all_empty:
            print("🎯 SUCCESS: All 7 application tables wiped. Schema & indexes preserved!")
        else:
            print("⚠️ WARNING: Some tables still contain records.")
        print("=" * 70)

    return all_empty


if __name__ == "__main__":
    success = wipe_database(verbose=True)
    sys.exit(0 if success else 1)
