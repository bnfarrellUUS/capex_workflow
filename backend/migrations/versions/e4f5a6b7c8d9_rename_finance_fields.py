"""rename finance fields: cost_permits -> cost_it_computer, po_number -> useful_life

Revision ID: e4f5a6b7c8d9
Revises: a9b8c7d6e5f4
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f5a6b7c8d9'
down_revision = 'a9b8c7d6e5f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.alter_column(
            'cost_permits', new_column_name='cost_it_computer',
            existing_type=sa.Numeric(precision=18, scale=2), existing_nullable=True)
        batch_op.alter_column(
            'po_number', new_column_name='useful_life',
            existing_type=sa.String(length=100), existing_nullable=True)


def downgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.alter_column(
            'cost_it_computer', new_column_name='cost_permits',
            existing_type=sa.Numeric(precision=18, scale=2), existing_nullable=True)
        batch_op.alter_column(
            'useful_life', new_column_name='po_number',
            existing_type=sa.String(length=100), existing_nullable=True)
