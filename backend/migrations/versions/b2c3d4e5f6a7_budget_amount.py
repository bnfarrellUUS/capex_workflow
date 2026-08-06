"""budget amount on capex requests

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "capex_requests",
        sa.Column("budget_amount", sa.Numeric(precision=18, scale=2), nullable=True),
    )


def downgrade():
    op.drop_column("capex_requests", "budget_amount")
