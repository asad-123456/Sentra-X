"""0001 – Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-22

Creates all 7 tables, indexes (SRS §7.3), and the immutable audit trigger
(FR-6 / SOC 2 / ISO 27001) for the Sentra-X platform.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extension: pgcrypto provides gen_random_uuid()
    # ------------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # ------------------------------------------------------------------
    # Table: users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "role IN ('Analyst', 'TeamLead', 'Admin')",
            name="ck_users_role",
        ),
    )

    # ------------------------------------------------------------------
    # Table: assets
    # ------------------------------------------------------------------
    op.create_table(
        "assets",
        sa.Column("agent_id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("criticality_tier", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "criticality_tier IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_assets_criticality_tier",
        ),
    )

    # ------------------------------------------------------------------
    # Table: alerts
    # ------------------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("wazuh_alert_id", sa.String(128), nullable=False),
        sa.Column("rule_id", sa.String(32), nullable=False),
        sa.Column("rule_level", sa.Integer(), nullable=False),
        sa.Column("rule_description", sa.Text(), nullable=False),
        sa.Column(
            "mitre_tactics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "mitre_techniques",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("src_ip", sa.String(45), nullable=True),
        sa.Column("process_signature", sa.Text(), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(32),
            server_default=sa.text("'PENDING_REVIEW'"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("wazuh_alert_id", name="uq_alerts_wazuh_alert_id"),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["assets.agent_id"],
            name="fk_alerts_agent_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW','AWAITING_ANALYST','NEEDS_MANUAL_TRIAGE','ESCALATED','CLOSED')",
            name="ck_alerts_status",
        ),
    )

    # ------------------------------------------------------------------
    # Table: evidence_packs
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_packs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pack_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "valid_dot_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "injection_suspect",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "injected_exemplar_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # Decision 8.5: REQUIRED
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("alert_id", name="uq_evidence_packs_alert_id"),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name="fk_evidence_packs_alert_id",
            ondelete="CASCADE",
        ),
    )

    # ------------------------------------------------------------------
    # Table: ai_assessments
    # ------------------------------------------------------------------
    op.create_table(
        "ai_assessments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_verdict", sa.String(32), nullable=False),
        sa.Column("raw_severity", sa.String(16), nullable=False),
        sa.Column("effective_verdict", sa.String(32), nullable=False),
        sa.Column("effective_severity", sa.String(16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column(
            "cited_evidence_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "safety_floor_triggered",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "abstention_triggered",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column("guardrail_audit_note", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.String(32), nullable=True),
        sa.Column("model_name", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # Decision 8.5: REQUIRED
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("alert_id", name="uq_ai_assessments_alert_id"),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name="fk_ai_assessments_alert_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "raw_verdict IN ('TRUE_POSITIVE','FALSE_POSITIVE','NEEDS_ANALYST_REVIEW')",
            name="ck_ai_assessments_raw_verdict",
        ),
        sa.CheckConstraint(
            "raw_severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_ai_assessments_raw_severity",
        ),
    )

    # ------------------------------------------------------------------
    # Table: analyst_decisions_audit  (APPEND-ONLY – no updated_at)
    # ------------------------------------------------------------------
    op.create_table(
        "analyst_decisions_audit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_taken", sa.String(32), nullable=False),
        sa.Column("previous_verdict", sa.String(32), nullable=True),
        sa.Column("previous_severity", sa.String(16), nullable=True),
        sa.Column("final_verdict", sa.String(32), nullable=True),
        sa.Column("final_severity", sa.String(16), nullable=True),
        sa.Column(
            "rationale",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "exemplar_created",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # NO updated_at – append-only table enforced by trigger below.
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name="fk_audit_alert_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_user_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action_taken IN ('APPROVE','OVERRIDE','ESCALATE','RETRY_AI','MANUAL_TRIAGE_CLOSE','RESOLVE_ESCALATION')",
            name="ck_audit_action_taken",
        ),
    )

    # ------------------------------------------------------------------
    # Table: feedback_exemplars  (Decision 8.4: INTEGER SERIAL PK)
    # ------------------------------------------------------------------
    op.create_table(
        "feedback_exemplars",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("source_alert_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rule_id", sa.String(32), nullable=False),
        sa.Column("process_signature", sa.Text(), nullable=False),
        sa.Column("asset_criticality", sa.String(16), nullable=False),
        sa.Column("calibrated_verdict", sa.String(32), nullable=False),
        sa.Column("calibrated_severity", sa.String(16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column(
            "match_hit_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_alert_id"],
            ["alerts.id"],
            name="fk_exemplars_source_alert_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_exemplars_created_by",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "asset_criticality IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_exemplars_asset_criticality",
        ),
        sa.CheckConstraint(
            "calibrated_verdict IN ('TRUE_POSITIVE','FALSE_POSITIVE')",
            name="ck_exemplars_calibrated_verdict",
        ),
    )

    # ------------------------------------------------------------------
    # Indexes (SRS §7.3)
    # Note: uq_alerts_wazuh_alert_id is already created via UniqueConstraint on alerts
    # ------------------------------------------------------------------

    # 1. 24-hour temporal correlation index
    op.execute(
        "CREATE INDEX ix_alerts_agent_src_ts ON alerts(agent_id, src_ip, ingested_at DESC);"
    )

    # 3. FR-5 queue sort index
    op.execute(
        "CREATE INDEX ix_alerts_queue_priority ON alerts(status, rule_level DESC, ingested_at ASC);"
    )

    # 4. AI assessments → alert_id lookup
    op.execute(
        "CREATE INDEX ix_ai_assessments_alert_id ON ai_assessments(alert_id);"
    )

    # 5. Evidence packs → alert_id lookup
    op.execute(
        "CREATE INDEX ix_evidence_packs_alert_id ON evidence_packs(alert_id);"
    )

    # 6. Audit → alert_id lookup
    op.execute(
        "CREATE INDEX ix_audit_alert_id ON analyst_decisions_audit(alert_id);"
    )

    # 7. Audit → user_id lookup
    op.execute(
        "CREATE INDEX ix_audit_user_id ON analyst_decisions_audit(user_id);"
    )

    # 8. Sub-50ms exemplar retrieval (NFR-4, FR-4) – partial composite
    op.execute(
        "CREATE INDEX ix_exemplars_retrieval ON feedback_exemplars"
        "(rule_id, asset_criticality, created_at DESC) WHERE is_active = TRUE;"
    )

    # ------------------------------------------------------------------
    # Immutable audit trigger (T-DB-4 / FR-6 / SOC 2 / ISO 27001)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'analyst_decisions_audit is append-only. UPDATE and DELETE operations are permanently prohibited on this table (FR-6, NFR-4, SOC 2 / ISO 27001 compliance).';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_audit_immutability
        BEFORE UPDATE OR DELETE ON analyst_decisions_audit
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
        """
    )


# ---------------------------------------------------------------------------
# Downgrade – drop in reverse FK dependency order
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Drop trigger and function first
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutability ON analyst_decisions_audit;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification();")

    # Drop named indexes that were created outside op.create_table
    for idx in [
        "ix_exemplars_retrieval",
        "ix_audit_user_id",
        "ix_audit_alert_id",
        "ix_evidence_packs_alert_id",
        "ix_ai_assessments_alert_id",
        "ix_alerts_queue_priority",
        "ix_alerts_agent_src_ts",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {idx};")

    # Drop tables in reverse FK dependency order
    op.drop_table("feedback_exemplars")
    op.drop_table("analyst_decisions_audit")
    op.drop_table("ai_assessments")
    op.drop_table("evidence_packs")
    op.drop_table("alerts")
    op.drop_table("assets")
    op.drop_table("users")
