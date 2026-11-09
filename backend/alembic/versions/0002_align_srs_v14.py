"""0002 – Align schema with SRS v1.4

Revision ID: 0002_align_srs_v14
Revises: 0001_initial_schema
Create Date: 2026-10-28

Adds missing columns and constraints per SRS v1.4 Section 7.2.1:
- assets: updated_by (FK users.id)
- alerts: agent_name, alert_timestamp, retry_count
- ai_assessments: inference_latency_ms (synced with latency_ms)
- feedback_exemplars: revoked_by (FK users.id), revoked_at
- analyst_decisions_audit: support MANUAL_TRIAGE_CLOSURE in ck_audit_action_taken
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_align_srs_v14"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. assets: add updated_by
    op.add_column(
        "assets",
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_assets_updated_by",
        "assets",
        "users",
        ["updated_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2. alerts: add agent_name, alert_timestamp, retry_count
    op.add_column(
        "alerts",
        sa.Column(
            "agent_name",
            sa.String(255),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    # Populate existing alerts.agent_name from assets.hostname
    op.execute(
        """
        UPDATE alerts
        SET agent_name = assets.hostname
        FROM assets
        WHERE alerts.agent_id = assets.agent_id;
        """
    )

    op.add_column(
        "alerts",
        sa.Column(
            "alert_timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "retry_count",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    # 3. ai_assessments: add inference_latency_ms
    op.add_column(
        "ai_assessments",
        sa.Column(
            "inference_latency_ms",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE ai_assessments
        SET inference_latency_ms = latency_ms
        WHERE latency_ms IS NOT NULL;
        """
    )

    # 4. feedback_exemplars: add revoked_by, revoked_at
    op.add_column(
        "feedback_exemplars",
        sa.Column(
            "revoked_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_exemplars_revoked_by",
        "feedback_exemplars",
        "users",
        ["revoked_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "feedback_exemplars",
        sa.Column(
            "revoked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # 5. analyst_decisions_audit: update check constraint for action_taken
    op.drop_constraint("ck_audit_action_taken", "analyst_decisions_audit", type_="check")
    op.create_check_constraint(
        "ck_audit_action_taken",
        "analyst_decisions_audit",
        "action_taken IN ('APPROVE','OVERRIDE','ESCALATE','RETRY_AI','MANUAL_TRIAGE_CLOSE','MANUAL_TRIAGE_CLOSURE','RESOLVE_ESCALATION')",
    )


def downgrade() -> None:
    # Revert check constraint
    op.drop_constraint("ck_audit_action_taken", "analyst_decisions_audit", type_="check")
    op.create_check_constraint(
        "ck_audit_action_taken",
        "analyst_decisions_audit",
        "action_taken IN ('APPROVE','OVERRIDE','ESCALATE','RETRY_AI','MANUAL_TRIAGE_CLOSE','RESOLVE_ESCALATION')",
    )

    # Revert feedback_exemplars
    op.drop_constraint("fk_exemplars_revoked_by", "feedback_exemplars", type_="foreignkey")
    op.drop_column("feedback_exemplars", "revoked_at")
    op.drop_column("feedback_exemplars", "revoked_by")

    # Revert ai_assessments
    op.drop_column("ai_assessments", "inference_latency_ms")

    # Revert alerts
    op.drop_column("alerts", "retry_count")
    op.drop_column("alerts", "alert_timestamp")
    op.drop_column("alerts", "agent_name")

    # Revert assets
    op.drop_constraint("fk_assets_updated_by", "assets", type_="foreignkey")
    op.drop_column("assets", "updated_by")

