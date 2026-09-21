"""add users.entra_oid

Pinned on a user's first SSO sign-in and compared on every one after, so a
recycled or reassigned email address cannot inherit an existing user's roles,
division scope and authorship of approval-history rows.

Nullable, and deliberately NOT unique: the row is located by email and this
column only confirms it is the same person. See b8c9d0e1f2a3 for why a
nullable-unique column is a trap on SQL Server.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('entra_oid', sa.String(length=36), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('entra_oid')
