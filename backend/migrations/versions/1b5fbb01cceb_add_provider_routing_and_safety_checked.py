"""add provider routing and safety_checked

Adds per-version provider routing, and splits "safety was checked" from
"safety passed" so an output nobody could moderate is not recorded as clean.

Revision ID: 1b5fbb01cceb
Revises: 730ade2167f4
Create Date: 2026-09-12 17:01:40.324791
"""
import sqlalchemy as sa
from alembic import op

revision = "1b5fbb01cceb"
down_revision = "730ade2167f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Server defaults are required: these tables already hold rows, and the
    # columns are NOT NULL. Existing evaluations were produced when every
    # configured provider could moderate, so backfilling safety_checked to
    # true is accurate for them.
    op.add_column(
        "evaluation_results",
        sa.Column(
            "safety_checked", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "evaluation_results",
        sa.Column(
            "evaluation_provider", sa.String(length=20), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "workflow_versions",
        sa.Column("provider", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_versions", "provider")
    op.drop_column("evaluation_results", "evaluation_provider")
    op.drop_column("evaluation_results", "safety_checked")
