"""regions + division.region_id

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "regions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "region_vp_approvers",
        sa.Column("region_id", sa.String(36), sa.ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
    )
    with op.batch_alter_table("divisions") as batch:
        batch.add_column(sa.Column("region_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_divisions_region", "regions", ["region_id"], ["id"])


def downgrade():
    with op.batch_alter_table("divisions") as batch:
        batch.drop_constraint("fk_divisions_region", type_="foreignkey")
        batch.drop_column("region_id")
    op.drop_table("region_vp_approvers")
    op.drop_table("regions")
