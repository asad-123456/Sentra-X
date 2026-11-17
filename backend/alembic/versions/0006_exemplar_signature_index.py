"""0006 - partial index for Tier 1 exemplar lookup (rule_id + process_signature)

Revision ID: 0006_exemplar_signature_index
Revises: 0005_abr_audit_hardening
Create Date: 2026-11-18

ix_exemplars_retrieval covers (rule_id, asset_criticality, created_at DESC), which serves Tier 2. Tier 1 filters on
rule_id AND process_signature, so it gets its own partial index on ACTIVE rows (approved by Asad, NFR-4 / FR-4).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_exemplar_signature_index"
down_revision = "0005_abr_audit_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_exemplars_signature_lookup",
        "feedback_exemplars",
        ["rule_id", "process_signature", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("ix_exemplars_signature_lookup", table_name="feedback_exemplars")
