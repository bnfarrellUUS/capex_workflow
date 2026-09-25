"""approver pools keep their order: add position to the three pool tables

The admin screens let an approver pool be reordered (the first approver is the
request's "assigned to"), but the association tables stored only membership,
so the order came back as whatever the database returned. Existing rows get
position 0; an admin re-saving a pool sets the real order.

Revision ID: a1b2c3d4e5f7
Revises: c9d0e1f2a3b4
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f7'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None

TABLES = ('division_l1_approvers', 'region_vp_approvers', 'threshold_approvers')


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('position', sa.Integer(), nullable=False,
                                          server_default='0'))


def downgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            # SQL Server attaches an auto-named DEFAULT constraint to the
            # column, which must go first or the drop fails.
            batch_op.drop_column('position', mssql_drop_default=True)
