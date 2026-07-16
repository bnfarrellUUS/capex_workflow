"""split useful_life into useful_life_years + useful_life_months

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('useful_life_years', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('useful_life_months', sa.Integer(), nullable=True))
        batch_op.drop_column('useful_life')


def downgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('useful_life', sa.String(length=100), nullable=True))
        batch_op.drop_column('useful_life_months')
        batch_op.drop_column('useful_life_years')
