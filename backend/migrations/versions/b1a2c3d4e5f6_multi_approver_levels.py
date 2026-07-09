"""multiple approvers per level

Adds join tables so each approval level can have multiple approvers (any one
may act): division_l1_approvers (L1, per division) and threshold_approvers
(L2/L3). Existing single approvers (divisions.l1_approver_id,
approval_thresholds.approver_id) are copied into the new tables.

The legacy single-approver columns are intentionally left in place — they are
no longer mapped by the models (so harmless) and dropping FK-bearing columns is
risky on SQL Server. They can be removed in a later dedicated migration.

Revision ID: b1a2c3d4e5f6
Revises: 5ee3b5f4876c
"""
from alembic import op
import sqlalchemy as sa

revision = "b1a2c3d4e5f6"
down_revision = "5ee3b5f4876c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "division_l1_approvers",
        sa.Column("division_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("division_id", "user_id"),
    )
    op.create_table(
        "threshold_approvers",
        sa.Column("threshold_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["threshold_id"], ["approval_thresholds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("threshold_id", "user_id"),
    )
    # Copy existing single approvers into the new lists.
    op.execute(
        "INSERT INTO division_l1_approvers (division_id, user_id) "
        "SELECT id, l1_approver_id FROM divisions WHERE l1_approver_id IS NOT NULL"
    )
    op.execute(
        "INSERT INTO threshold_approvers (threshold_id, user_id) "
        "SELECT id, approver_id FROM approval_thresholds WHERE approver_id IS NOT NULL"
    )


def downgrade():
    op.drop_table("threshold_approvers")
    op.drop_table("division_l1_approvers")
