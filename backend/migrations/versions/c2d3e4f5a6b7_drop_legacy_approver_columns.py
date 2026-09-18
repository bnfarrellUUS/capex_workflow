"""drop legacy single-approver columns

Removes divisions.l1_approver_id and approval_thresholds.approver_id, now that
approvers live in the division_l1_approvers / threshold_approvers join tables
(migration b1a2c3d4e5f6 already copied the data across).

Dropping FK-bearing columns is dialect-specific:
- SQLite (dev): batch_alter_table recreates the table without the column,
  handling the foreign keys automatically.
- SQL Server (prod): drop the foreign key constraint first, then the column.
  Both FKs are looked up in sys.foreign_keys rather than assumed: the
  approval_thresholds one was created unnamed, and the divisions one is
  declared use_alter=True in 5ee3b5f4876c, which makes op.create_table omit it
  from the CREATE TABLE without emitting the follow-up ALTER — so on SQL Server
  fk_division_l1_approver does not exist at all and dropping it by name failed
  with "'fk_division_l1_approver' is not a constraint" (3728).

Revision ID: c2d3e4f5a6b7
Revises: b1a2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


def _fk_on(bind, table, column):
    """Name of the foreign key on table.column, or None if there isn't one."""
    return bind.execute(sa.text(
        "SELECT fk.name FROM sys.foreign_keys fk "
        "JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id "
        "JOIN sys.columns c ON c.object_id = fkc.parent_object_id "
        "AND c.column_id = fkc.parent_column_id "
        "WHERE fk.parent_object_id = OBJECT_ID(:table) AND c.name = :column"
    ), {"table": table, "column": column}).scalar()


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("divisions") as batch:
            batch.drop_column("l1_approver_id")
        with op.batch_alter_table("approval_thresholds") as batch:
            batch.drop_column("approver_id")
        return

    # SQL Server (and other non-SQLite dialects): drop FKs before the columns.
    for table, column in (("divisions", "l1_approver_id"),
                          ("approval_thresholds", "approver_id")):
        fk_name = _fk_on(bind, table, column)
        if fk_name:
            op.drop_constraint(fk_name, table, type_="foreignkey")
        op.drop_column(table, column)


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
