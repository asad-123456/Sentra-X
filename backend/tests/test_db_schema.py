from __future__ import annotations

import sys
import os

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uuid
from sqlalchemy import text
from app.database import SyncSessionLocal, sync_engine


def test_schema_and_immutability_trigger():
    print("=" * 70)
    print("SENTRA-X POSTGRESQL 16 SCHEMA & IMMUTABILITY TRIGGER TEST (SRS v1.4)")
    print("=" * 70)

    with SyncSessionLocal() as session:
        # 1. Verify all 7 tables exist in information_schema
        expected_tables = {
            "users",
            "assets",
            "alerts",
            "evidence_packs",
            "ai_assessments",
            "analyst_decisions_audit",
            "feedback_exemplars",
        }
        res = session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public';"
            )
        )
        existing_tables = {row[0] for row in res.fetchall()}
        missing = expected_tables - existing_tables
        assert not missing, f"Missing tables in database: {missing}"
        print(f"✅ PASS: All 7 Core Tables exist ({', '.join(sorted(expected_tables))})")

        # 2. Verify SRS v1.4 Columns in Schema
        print("\n--- Verifying SRS v1.4 Column Parity ---")
        expected_columns = {
            ("assets", "updated_by"),
            ("alerts", "agent_name"),
            ("alerts", "alert_timestamp"),
            ("alerts", "retry_count"),
            ("ai_assessments", "inference_latency_ms"),
            ("feedback_exemplars", "user_id"),
            ("feedback_exemplars", "revoked_by"),
            ("feedback_exemplars", "revoked_at"),
        }
        col_res = session.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public';"
            )
        )
        existing_columns = {(row[0], row[1]) for row in col_res.fetchall()}
        missing_cols = expected_columns - existing_columns
        assert not missing_cols, f"Missing SRS v1.4 columns: {missing_cols}"
        print(f"✅ PASS: All SRS v1.4 columns verified ({len(expected_columns)} checked):")
        for tbl, col in sorted(expected_columns):
            print(f"   -> {tbl}.{col}")

        # 3. Verify High-Speed Indexes
        print("\n--- Verifying High-Speed Composite & Partial Indexes ---")
        expected_indexes = {
            "ix_exemplars_retrieval",
            "ix_alerts_queue_priority",
            "ix_alerts_agent_src_ts",
            "ix_ai_assessments_alert_id",
            "ix_evidence_packs_alert_id",
            "ix_audit_alert_id",
            "ix_audit_user_id",
            "uq_alerts_wazuh_alert_id",
        }
        res = session.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public';"
            )
        )
        existing_indexes = {row[0] for row in res.fetchall()}
        missing_idx = expected_indexes - existing_indexes
        assert not missing_idx, f"Missing indexes: {missing_idx}"
        print(f"✅ PASS: High-Speed Composite & Partial Indexes Verified ({len(expected_indexes)} checked)")

        # 4. Verify SRS v1.4 Check Constraints
        print("\n--- Verifying SRS v1.4 Check Constraints ---")
        expected_constraints = {
            "ck_users_role",
            "ck_assets_criticality_tier",
            "ck_alerts_status",
            "ck_alerts_rule_level",
            "ck_alerts_retry_count",
            "ck_ai_assessments_raw_verdict",
            "ck_ai_assessments_raw_severity",
            "ck_ai_assessments_confidence_score",
            "ck_ai_assessments_retry_count",
            "ck_exemplars_asset_criticality",
            "ck_exemplars_calibrated_verdict",
            "ck_exemplars_rationale_length",
            "ck_audit_action_taken",
        }
        ck_res = session.execute(
            text(
                "SELECT conname FROM pg_constraint WHERE conname LIKE 'ck_%';"
            )
        )
        existing_ck = {row[0] for row in ck_res.fetchall()}
        missing_ck = expected_constraints - existing_ck
        assert not missing_ck, f"Missing SRS v1.4 check constraints: {missing_ck}"
        print(f"✅ PASS: All {len(expected_constraints)} SRS v1.4 Check Constraints Verified")

        # 4. Test Immutability Trigger (FR-6 / SOC 2 / ISO 27001)
        print("\n--- Testing Analyst Decisions Audit Immutability Trigger ---")
        
        # Fetch valid existing user and alert for foreign key integrity
        row_user = session.execute(text("SELECT id FROM users LIMIT 1;")).fetchone()
        test_uid = row_user[0]

        row_alert = session.execute(text("SELECT id FROM alerts LIMIT 1;")).fetchone()
        test_aid = row_alert[0]

        # Step 4a: Insert audit record (Must Succeed)
        audit_id = uuid.uuid4()
        session.execute(
            text(
                "INSERT INTO analyst_decisions_audit (id, alert_id, user_id, action_taken, final_verdict, final_severity, rationale) "
                "VALUES (:id, :alert_id, :user_id, 'APPROVE', 'TRUE_POSITIVE', 'HIGH', 'Initial valid decision approval');"
            ),
            {"id": audit_id, "alert_id": test_aid, "user_id": test_uid},
        )
        session.commit()
        print("✅ PASS: Audit record successfully inserted into analyst_decisions_audit.")

        # Step 4b: Attempt UPDATE on audit record (MUST BE BLOCKED BY TRIGGER)
        update_blocked = False
        try:
            session.execute(
                text(
                    "UPDATE analyst_decisions_audit SET rationale = 'TAMPERED RATIONALE' WHERE id = :id;"
                ),
                {"id": audit_id},
            )
            session.commit()
        except Exception as e:
            session.rollback()
            if "append-only" in str(e) or "trg_audit_immutability" in str(e):
                update_blocked = True
                print(f"✅ PASS: UPDATE operation strictly blocked by trigger:\n   -> {e}")
            else:
                assert False, f"Unexpected error during UPDATE: {e}"

        assert update_blocked, "UPDATE was not blocked by trigger! Immutability violation."

        # Step 4c: Attempt DELETE on audit record (MUST BE BLOCKED BY TRIGGER)
        delete_blocked = False
        try:
            session.execute(
                text(
                    "DELETE FROM analyst_decisions_audit WHERE id = :id;"
                ),
                {"id": audit_id},
            )
            session.commit()
        except Exception as e:
            session.rollback()
            if "append-only" in str(e) or "trg_audit_immutability" in str(e):
                delete_blocked = True
                print(f"✅ PASS: DELETE operation strictly blocked by trigger:\n   -> {e}")
            else:
                assert False, f"Unexpected error during DELETE: {e}"

        assert delete_blocked, "DELETE was not blocked by trigger! Immutability violation."

        print("\n" + "=" * 70)
        print("🎯 ALL POSTGRESQL 16 SCHEMA, SRS v1.4 PARITY & TRIGGER TESTS PASSED!")
        print("=" * 70)


if __name__ == "__main__":
    success = test_schema_and_immutability_trigger()
    if not success:
        sys.exit(1)
