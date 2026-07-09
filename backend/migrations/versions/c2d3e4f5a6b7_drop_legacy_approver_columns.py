"""drop legacy single-approver columns

Removes divisions.l1_approver_id and approval_thresholds.approver_id, now that
approvers live in the division_l1_approvers / threshold_approvers join tables
(migration b1a2c3d4e5f6 already copied the data across).

Dropping FK-bearing columns is dialect-specific:
- SQLite (dev): batch_alter_table recreates the table without the column,
  handling the foreign keys automatically.
- SQL Server (prod): drop the foreign key constraint first, then the column.
  divisions' FK is named (fk_division_l1_approver); approval_thresholds' FK was
  created unnamed, so look up its DB-generated name.

Revision ID: c2d3e4f5a6b7
Revises: b1a2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("divisions") as batch:
            batch.drop_column("l1_approver_id")
        with op.batch_alter_table("approval_thresholds") as batch:
            batch.drop_column("approver_id")
        return

    # SQL Server (and other non-SQLite dialects): drop FKs before the columns.
    op.drop_constraint("fk_division_l1_approver", "divisions", type_="foreignkey")
    op.drop_column("divisions", "l1_approver_id")

    fk_name = bind.execute(sa.text(
        "SELECT fk.name FROM sys.foreign_keys fk "
        "JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id "
        "JOIN sys.columns c ON c.object_id = fkc.parent_object_id "
        "AND c.column_id = fkc.parent_column_id "
        "WHERE fk.parent_object_id = OBJECT_ID('approval_thresholds') "
        "AND c.name = 'approver_id'"
    )).scalar()
    if fk_name:
        op.drop_constraint(fk_name, "approval_thresholds", type_="foreignkey")
    op.drop_column("approval_thresholds", "approver_id")


def downgrade():
    # Restores the columns (empty); the approver data lives in the join tables.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("divisions") as batch:
            batch.add_column(sa.Column("l1_approver_id", sa.String(length=36), nullable=True))
        with op.batch_alter_table("approval_thresholds") as batch:
            batch.add_column(sa.Column("approver_id", sa.String(length=36), nullable=True))
        return

    op.add_column("divisions", sa.Column("l1_approver_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_division_l1_approver", "divisions", "users",
                          ["l1_approver_id"], ["id"], ondelete="NO ACTION")
    op.add_column("approval_thresholds", sa.Column("approver_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(None, "approval_thresholds", "users",
                          ["approver_id"], ["id"], ondelete="NO ACTION")
