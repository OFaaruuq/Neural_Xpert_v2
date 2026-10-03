"""Record the IP address of each public page view

Revision ID: b7e2c4a91d08
Revises: a91c4e2b7d10
Create Date: 2026-10-03 20:15:00

"""
import sqlalchemy as sa
from alembic import op


revision = "b7e2c4a91d08"
down_revision = "a91c4e2b7d10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "page_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_page_visits_visited_at", "page_visits", ["visited_at"])
    op.create_index("ix_page_visits_ip_address", "page_visits", ["ip_address"])
    op.create_index("ix_page_visits_visitor_hash", "page_visits", ["visitor_hash"])


def downgrade():
    op.drop_index("ix_page_visits_visitor_hash", table_name="page_visits")
    op.drop_index("ix_page_visits_ip_address", table_name="page_visits")
    op.drop_index("ix_page_visits_visited_at", table_name="page_visits")
    op.drop_table("page_visits")
