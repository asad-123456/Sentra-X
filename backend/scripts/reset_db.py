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
from app.database import sync_engine
from app.seed_data import seed_database
from wipe_db import wipe_database

EXPECTED_COUNTS = {
    "users": 3,
    "assets": 6,
    "alerts": 16,
    "evidence_packs": 12,
    "ai_assessments": 12,
    "analyst_decisions_audit": 3,
    "feedback_exemplars": 4,
    "system_configurations": 1,
}


def reset_database() -> bool:
    """Wipes the database and re-seeds it with original mock data from demo_seed.json.
    
    Used for live demonstrations and testing to return to a known pristine state.
    """
    print("=" * 70)
    print("SENTRA-X DATABASE RESET (DEMONSTRATION & INTEGRATION READY)")
    print("=" * 70)
    
    print("\n[Step 1/2] Purging existing database records...")
    wiped = wipe_database(verbose=False)
    if not wiped:
        print("❌ Error during table purge.")
        return False
    print("✅ All tables cleanly truncated. Sequences reset to 1.")

    print("\n[Step 2/2] Seeding baseline telemetry from demo_seed.json...")
    seeded = seed_database()
    if not seeded:
        print("❌ Error during database seeding.")
        return False

    # Verify final counts
    print("\n" + "-" * 70)
    print("BASELINE INTEGRITY VERIFICATION:")
    print("-" * 70)
    
    all_matched = True
    with sync_engine.connect() as conn:
        for table, expected in EXPECTED_COUNTS.items():
            actual = conn.execute(text(f"SELECT count(*) FROM {table};")).scalar()
            match = actual == expected
            if not match:
                all_matched = False
            status = "✅ OK" if match else f"⚠️ MISMATCH (Expected {expected})"
            print(f"  • {table:<25} : {actual:>3} rows [{status}]")

    print("\n" + "=" * 70)
    if all_matched:
        print("🎯 DATABASE RESET COMPLETE: 100% Match with Demonstration Baseline!")
    else:
        print("⚠️ Reset completed with discrepancies in row counts.")
    print("=" * 70)

    return all_matched


if __name__ == "__main__":
    success = reset_database()
    sys.exit(0 if success else 1)
