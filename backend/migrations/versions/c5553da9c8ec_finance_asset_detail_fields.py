"""finance asset detail fields

Revision ID: c5553da9c8ec
Revises: d3e4f5a6b7c8
Create Date: 2026-07-14 15:29:18.618922

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5553da9c8ec'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('asset_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('gl_account', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('po_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('in_service_date', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.drop_column('in_service_date')
        batch_op.drop_column('po_number')
        batch_op.drop_column('gl_account')
        batch_op.drop_column('asset_number')
