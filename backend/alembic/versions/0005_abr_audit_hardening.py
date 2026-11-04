"""0005 — Abdur Rehman audit hardening: index alignment, action normalization, and nullability fixes

Revision ID: 0005_abr_audit_hardening
Revises: 0004_add_system_configurations
Create Date: 2026-11-02

Performs schema alignments flagged during technical audit (abr_message_02112026.md and abr_message_04112026.md):
1. Replaces composite correlation index ix_alerts_agent_src_ts on (agent_id, src_ip, ingested_at)
   with dedicated timestamp indexes:
     - ix_alerts_agent_timestamp ON alerts (agent_id, alert_timestamp DESC)
     - ix_alerts_src_ip_timestamp ON alerts (src_ip, alert_timestamp DESC) WHERE src_ip IS NOT NULL
2. Hardens ck_audit_action_taken to drop legacy MANUAL_TRIAGE_CLOSE, standardizing strictly
   on MANUAL_TRIAGE_CLOSURE per SRS v1.4 data dictionary:
     - Bypasses trg_audit_immutability to migrate any pre-existing rows before applying the constraint.
3. Relaxes feedback_exemplars.process_signature to NULLABLE to accommodate human overrides
   on non-process Wazuh alerts (network scans, SSH brute force, firewall drops).
4. Relaxes assets.ip_address to NULLABLE to allow auto-registration of agents reporting
   without an IP address header.
5. Rewrites ix_alerts_queue_priority from prototype (status, rule_level DESC, ingested_at ASC)
   to (status, ingested_at ASC) matching FIFO queue discipline and active status filtering.
6. Deploys database synchronization trigger trg_sync_feedback_exemplar_user on feedback_exemplars
   to guarantee user_id (canonical SRS §7.2.1) and created_by (ORM relation) never drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_abr_audit_hardening"
down_revision = "0004_add_system_configurations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Alerts correlation indexes: drop flawed ingested_at index, add alert_timestamp indexes
    op.drop_index("ix_alerts_agent_src_ts", table_name="alerts")
    op.create_index(
        "ix_alerts_agent_timestamp",
        "alerts",
        ["agent_id", sa.text("alert_timestamp DESC")],
        unique=False,
    )
    op.create_index(
        "ix_alerts_src_ip_timestamp",
        "alerts",
        ["src_ip", sa.text("alert_timestamp DESC")],
        unique=False,
        postgresql_where=sa.text("src_ip IS NOT NULL"),
    )

    # 2. Audit check constraint: drop MANUAL_TRIAGE_CLOSE, retain MANUAL_TRIAGE_CLOSURE
    # Safely migrate existing rows by temporarily disabling the immutability trigger
    op.execute("ALTER TABLE analyst_decisions_audit DISABLE TRIGGER trg_audit_immutability;")
    op.execute(
        "UPDATE analyst_decisions_audit SET action_taken = 'MANUAL_TRIAGE_CLOSURE' "
        "WHERE action_taken = 'MANUAL_TRIAGE_CLOSE';"
    )
    op.execute("ALTER TABLE analyst_decisions_audit ENABLE TRIGGER trg_audit_immutability;")

    op.drop_constraint("ck_audit_action_taken", "analyst_decisions_audit", type_="check")
    op.create_check_constraint(
        "ck_audit_action_taken",
        "analyst_decisions_audit",
        "action_taken IN ('APPROVE','OVERRIDE','ESCALATE','RETRY_AI','MANUAL_TRIAGE_CLOSURE','RESOLVE_ESCALATION')",
    )

    # 3. Feedback exemplars: allow NULL process_signature for non-process alerts
    op.alter_column(
        "feedback_exemplars",
        "process_signature",
        existing_type=sa.Text(),
        nullable=True,
    )

    # 4. Assets: allow NULL ip_address for agent auto-registration without IP
    op.alter_column(
        "assets",
        "ip_address",
        existing_type=sa.String(length=45),
        nullable=True,
    )

    # 5. Alerts queue priority index: rewrite to (status, ingested_at ASC) matching queue discipline
    op.drop_index("ix_alerts_queue_priority", table_name="alerts")
    op.create_index(
        "ix_alerts_queue_priority",
        "alerts",
        ["status", sa.text("ingested_at ASC")],
        unique=False,
    )

    # 6. Synchronize user_id and created_by on feedback_exemplars to prevent drift
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_feedback_exemplar_user()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.user_id IS NOT NULL AND NEW.created_by IS NULL THEN
                NEW.created_by := NEW.user_id;
            ELSIF NEW.created_by IS NOT NULL AND NEW.user_id IS NULL THEN
                NEW.user_id := NEW.created_by;
            ELSIF NEW.user_id IS NOT NULL AND NEW.created_by IS NOT NULL THEN
                NEW.created_by := NEW.user_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_sync_feedback_exemplar_user ON feedback_exemplars;
        CREATE TRIGGER trg_sync_feedback_exemplar_user
        BEFORE INSERT OR UPDATE ON feedback_exemplars
        FOR EACH ROW EXECUTE FUNCTION sync_feedback_exemplar_user();
        """
    )


def downgrade() -> None:
    # 6. Drop exemplar user sync trigger
    op.execute("DROP TRIGGER IF EXISTS trg_sync_feedback_exemplar_user ON feedback_exemplars;")
    op.execute("DROP FUNCTION IF EXISTS sync_feedback_exemplar_user();")

    # 5. Alerts queue priority index: revert to prototype index
    op.drop_index("ix_alerts_queue_priority", table_name="alerts")
    op.create_index(
        "ix_alerts_queue_priority",
        "alerts",
        ["status", sa.text("rule_level DESC"), sa.text("ingested_at ASC")],
        unique=False,
    )

    # 4. Assets: revert ip_address to NOT NULL (filling nulls first)
    op.execute("UPDATE assets SET ip_address = '0.0.0.0' WHERE ip_address IS NULL;")
    op.alter_column(
        "assets",
        "ip_address",
        existing_type=sa.String(length=45),
        nullable=False,
    )

    # 3. Feedback exemplars: revert process_signature to NOT NULL
    op.execute("UPDATE feedback_exemplars SET process_signature = 'Unknown Process' WHERE process_signature IS NULL;")
    op.alter_column(
        "feedback_exemplars",
        "process_signature",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 2. Audit check constraint: restore both spellings
    op.drop_constraint("ck_audit_action_taken", "analyst_decisions_audit", type_="check")
    op.create_check_constraint(
        "ck_audit_action_taken",
        "analyst_decisions_audit",
        "action_taken IN ('APPROVE','OVERRIDE','ESCALATE','RETRY_AI','MANUAL_TRIAGE_CLOSE','MANUAL_TRIAGE_CLOSURE','RESOLVE_ESCALATION')",
    )

    # 1. Alerts correlation indexes: revert to ix_alerts_agent_src_ts
    op.drop_index("ix_alerts_src_ip_timestamp", table_name="alerts")
    op.drop_index("ix_alerts_agent_timestamp", table_name="alerts")
    op.create_index(
        "ix_alerts_agent_src_ts",
        "alerts",
        ["agent_id", "src_ip", sa.text("ingested_at DESC")],
        unique=False,
    )
