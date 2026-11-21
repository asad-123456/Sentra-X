"""Track which pending attempt may write an AI triage result."""

import sqlalchemy as sa
from alembic import op

revision = "0006_triage_generation"
down_revision = "0005_abr_audit_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("triage_generation", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("alerts", "triage_generation")
