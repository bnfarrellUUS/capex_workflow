"""admin reassign: capex_requests.reassigned_to_id

An ADMIN can name a per-request approver for the request's current level
(ADO 5907), for a request stuck because every approver at that level was
deactivated. Nullable and deliberately not unique: a nullable-unique column
allows only one NULL on SQL Server (see b8c9d0e1f2a3).

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a8'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reassigned_to_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_capex_requests_reassigned_to_id_users', 'users',
            ['reassigned_to_id'], ['id'], ondelete='NO ACTION')


def downgrade():
    with op.batch_alter_table('capex_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_capex_requests_reassigned_to_id_users', type_='foreignkey')
        batch_op.drop_column('reassigned_to_id')
