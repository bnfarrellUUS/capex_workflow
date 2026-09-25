"""users.session_version: an admin reset signs the user out everywhere

Part of the Flask-Login id, so bumping it voids the user's existing session
and remember-me cookies. NOT NULL with a server default of 0, so existing
rows need no backfill.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b9'
down_revision = 'b2c3d4e5f6a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_version', sa.Integer(), nullable=False,
                                      server_default='0'))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('session_version')
