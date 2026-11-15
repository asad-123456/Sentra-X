"""0003 — Add missing SRS v1.4 database check constraints and defaults

Revision ID: 0003_add_srs_check_constraints
Revises: 0002_align_srs_v14
Create Date: 2026-10-31

Adds exact check constraints and server defaults per SRS v1.4 Section 7.2.1:
- alerts:
    - ck_alerts_rule_level: CHECK (rule_level BETWEEN 0 AND 15)
    - ck_alerts_retry_count: CHECK (retry_count >= 0)
- ai_assessments:
    - ck_ai_assessments_confidence_score: CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
    - ck_ai_assessments_retry_count: CHECK (retry_count BETWEEN 0 AND 3)
- assets:
    - criticality_tier: server_default='MEDIUM'
- feedback_exemplars:
    - user_id: UUID foreign key to users.id (matching Data Dictionary table §7.2.1)
    - ck_exemplars_rationale_length: CHECK (length(rationale) >= 10)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_add_srs_check_constraints"
down_revision = "0002_align_srs_v14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. alerts: add rule_level (0..15) and retry_count (>= 0) check constraints
    op.create_check_constraint(
        "ck_alerts_rule_level",
        "alerts",
        "rule_level BETWEEN 0 AND 15",
    )
    op.create_check_constraint(
        "ck_alerts_retry_count",
        "alerts",
        "retry_count >= 0",
    )

    # 2. ai_assessments: add confidence_score (0.0..1.0) and retry_count (0..3) check constraints
    op.create_check_constraint(
        "ck_ai_assessments_confidence_score",
        "ai_assessments",
        "confidence_score >= 0.0 AND confidence_score <= 1.0",
    )
    op.create_check_constraint(
        "ck_ai_assessments_retry_count",
        "ai_assessments",
        "retry_count BETWEEN 0 AND 3",
    )

    # 3. assets: set server default 'MEDIUM' on criticality_tier per SRS v1.4 Data Dictionary
    op.alter_column(
        "assets",
        "criticality_tier",
        server_default=sa.text("'MEDIUM'"),
    )

    # 4. feedback_exemplars: add user_id FK users(id) and rationale length check (>= 10 chars)
    op.add_column(
        "feedback_exemplars",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_exemplars_user_id",
        "feedback_exemplars",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Synchronize user_id from created_by for existing rows
    op.execute(
        """
        UPDATE feedback_exemplars
        SET user_id = created_by
        WHERE user_id IS NULL AND created_by IS NOT NULL;
        """
    )
    op.create_check_constraint(
        "ck_exemplars_rationale_length",
        "feedback_exemplars",
        "length(rationale) >= 10",
    )


def downgrade() -> None:
    # Revert feedback_exemplars constraints and column
    op.drop_constraint("ck_exemplars_rationale_length", "feedback_exemplars", type_="check")
    op.drop_constraint("fk_exemplars_user_id", "feedback_exemplars", type_="foreignkey")
    op.drop_column("feedback_exemplars", "user_id")

    # Revert assets server_default
    op.alter_column(
        "assets",
        "criticality_tier",
        server_default=None,
    )

    # Revert ai_assessments check constraints
    op.drop_constraint("ck_ai_assessments_retry_count", "ai_assessments", type_="check")
    op.drop_constraint("ck_ai_assessments_confidence_score", "ai_assessments", type_="check")

    # Revert alerts check constraints
    op.drop_constraint("ck_alerts_retry_count", "alerts", type_="check")
    op.drop_constraint("ck_alerts_rule_level", "alerts", type_="check")

