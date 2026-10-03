"""Type, size, and color for the case studies page

Revision ID: d1a6f3c94e20
Revises: c8d4e1b72a05
Create Date: 2026-10-03 22:10:00

"""
import sqlalchemy as sa
from alembic import op


revision = "d1a6f3c94e20"
down_revision = "c8d4e1b72a05"
branch_labels = None
depends_on = None


def _integers(table, names):
    with op.batch_alter_table(table) as batch:
        for name in names:
            batch.add_column(sa.Column(name, sa.Integer(), nullable=False, server_default="0"))


def _strings(table, columns):
    with op.batch_alter_table(table) as batch:
        for name, length in columns:
            batch.add_column(sa.Column(name, sa.String(length=length), nullable=False, server_default=""))


def upgrade():
    _strings("site_pages", (("font_family", 40), ("heading_color", 20), ("body_color", 20)))
    _integers("site_pages", ("heading_size", "body_size", "tag_size"))
    _strings("case_studies", (("font_family", 40),))
    _integers("case_studies", ("title_size", "summary_size"))


def downgrade():
    with op.batch_alter_table("site_pages") as batch:
        for name in ("font_family", "heading_size", "body_size", "tag_size", "heading_color", "body_color"):
            batch.drop_column(name)
    with op.batch_alter_table("case_studies") as batch:
        for name in ("font_family", "title_size", "summary_size"):
            batch.drop_column(name)
