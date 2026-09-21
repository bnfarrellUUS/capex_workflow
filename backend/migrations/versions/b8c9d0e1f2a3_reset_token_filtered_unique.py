"""users.reset_token: filtered unique index on SQL Server

SQL Server treats NULLs as equal in a UNIQUE index and allows exactly one, so
the plain UNIQUE constraint on this nullable column capped the table at ONE
user with no reset token -- i.e. one user, full stop. Inserting a second failed
with "Violation of UNIQUE KEY constraint ... The duplicate key value is
(<NULL>)". A filtered unique index is the standard SQL Server idiom for a
nullable-unique column.

SQLite needs no change: it treats NULLs as distinct in a UNIQUE index, so many
users with no reset token are already legal there. That is why dev ran fine
with 19 users while Azure SQL held exactly one. The two dialects therefore
converge on the same behaviour rather than the same DDL.

Revision ID: b8c9d0e1f2a3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None

INDEX_NAME = 'uq_users_reset_token'


def _unique_constraint_on(bind, table, column):
    """Name of the UNIQUE constraint covering table.column, or None.

    SQL Server auto-generates the name (UQ__users__25F405EB36267CDA on the dev
    server) and it differs per database, so it must be looked up rather than
    assumed -- the same failure f3ed810 fixed for a foreign key.
    """
    return bind.execute(sa.text(
        "SELECT kc.name FROM sys.key_constraints kc "
        "JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id "
        "AND ic.index_id = kc.unique_index_id "
        "JOIN sys.columns c ON c.object_id = kc.parent_object_id "
        "AND c.column_id = ic.column_id "
        "WHERE kc.parent_object_id = OBJECT_ID(:table) AND kc.type = 'UQ' "
        "AND c.name = :column"
    ), {"table": table, "column": column}).scalar()


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        return
    name = _unique_constraint_on(bind, 'users', 'reset_token')
    if name:
        op.drop_constraint(name, 'users', type_='unique')
    op.create_index(INDEX_NAME, 'users', ['reset_token'], unique=True,
                    mssql_where=sa.text('reset_token IS NOT NULL'))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        return
    op.drop_index(INDEX_NAME, table_name='users')
    op.create_unique_constraint(INDEX_NAME, 'users', ['reset_token'])
