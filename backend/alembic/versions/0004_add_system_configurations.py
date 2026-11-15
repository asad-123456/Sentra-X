"""0004 — Add system_configurations table for multi-worker persistence

Revision ID: 0004_add_system_configurations
Revises: 0003_add_srs_check_constraints
Create Date: 2026-11-02

Creates the system_configurations table in PostgreSQL to ensure thread-safety
and persistent state synchronization across multi-worker uvicorn deployments
and container replicas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_add_system_configurations"
down_revision = "0003_add_srs_check_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_configurations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "wazuh_endpoint",
            sa.String(length=255),
            server_default=sa.text("'https://wazuh-master.sentrax.internal:55000'"),
            nullable=False,
        ),
        sa.Column(
            "wazuh_status",
            sa.String(length=32),
            server_default=sa.text("'CONNECTED'"),
            nullable=False,
        ),
        sa.Column(
            "polling_interval_seconds",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=False,
        ),
        sa.Column(
            "min_rule_level",
            sa.Integer(),
            server_default=sa.text("4"),
            nullable=False,
        ),
        sa.Column(
            "llm_provider",
            sa.String(length=32),
            server_default=sa.text("'Gemini'"),
            nullable=False,
        ),
        sa.Column(
            "model_name",
            sa.String(length=64),
            server_default=sa.text("'gemini-3.1-flash-lite'"),
            nullable=False,
        ),
        sa.Column(
            "abstention_threshold",
            sa.Float(),
            server_default=sa.text("0.6"),
            nullable=False,
        ),
        sa.Column(
            "max_exemplars_injected",
            sa.Integer(),
            server_default=sa.text("2"),
            nullable=False,
        ),
        sa.Column(
            "last_sync_timestamp",
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
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert default singleton configuration row
    op.execute(
        """
        INSERT INTO system_configurations (
            id, wazuh_endpoint, wazuh_status, polling_interval_seconds, min_rule_level,
            llm_provider, model_name, abstention_threshold, max_exemplars_injected,
            last_sync_timestamp, updated_at
        ) VALUES (
            1,
            'https://wazuh-master.sentrax.internal:55000',
            'CONNECTED',
            30,
            4,
            'Gemini',
            'gemini-3.1-flash-lite',
            0.6,
            2,
            NOW(),
            NOW()
        ) ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("system_configurations")
