"""pings + ping_recipients: in-app messaging

Purely additive -- no existing table is altered and nothing is backfilled.
A reply is a child row via pings.parent_id, never a separate table.

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("pings.id"), nullable=True),
        sa.Column("sender_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(36),
                  sa.ForeignKey("capex_requests.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pings_parent_id", "pings", ["parent_id"])
    op.create_index("ix_pings_sender_id", "pings", ["sender_id"])
    op.create_index("ix_pings_request_id", "pings", ["request_id"])
    op.create_table(
        "ping_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ping_id", sa.String(36),
                  sa.ForeignKey("pings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("ping_id", "user_id", name="uq_ping_recipient"),
    )
    op.create_index("ix_ping_recipients_user_id", "ping_recipients", ["user_id"])


def downgrade():
    op.drop_index("ix_ping_recipients_user_id", table_name="ping_recipients")
    op.drop_table("ping_recipients")
    op.drop_index("ix_pings_request_id", table_name="pings")
    op.drop_index("ix_pings_sender_id", table_name="pings")
    op.drop_index("ix_pings_parent_id", table_name="pings")
    op.drop_table("pings")
