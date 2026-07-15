"""drop users.username — email is the sole login identifier

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa


revision = 'a9b8c7d6e5f4'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "mssql":
        # The initial schema's UNIQUE(username) constraint is unnamed, so SQL
        # Server gave it a generated name; find and drop it before the column.
        rows = bind.exec_driver_sql(
            "SELECT kc.name FROM sys.key_constraints kc "
            "JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id "
            " AND ic.index_id = kc.unique_index_id "
            "JOIN sys.columns c ON c.object_id = ic.object_id "
            " AND c.column_id = ic.column_id "
            "WHERE kc.parent_object_id = OBJECT_ID('users') "
            " AND kc.type = 'UQ' AND c.name = 'username'"
        ).fetchall()
        for (name,) in rows:
            op.execute(f"ALTER TABLE users DROP CONSTRAINT [{name}]")
    # SQLite: batch mode recreates the table, dropping the constraint with it.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('username')


def downgrade():
    # Restored as nullable (original values are gone); uniqueness not restored.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(length=150), nullable=True))
