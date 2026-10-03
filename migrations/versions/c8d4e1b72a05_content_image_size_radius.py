"""Store display size and corner radius for content images

Revision ID: c8d4e1b72a05
Revises: b7e2c4a91d08
Create Date: 2026-10-03 20:25:00

"""
import sqlalchemy as sa
from alembic import op


revision = "c8d4e1b72a05"
down_revision = "b7e2c4a91d08"
branch_labels = None
depends_on = None


def _add(table, columns):
    with op.batch_alter_table(table) as batch:
        for name, default in columns:
            batch.add_column(sa.Column(name, sa.Integer(), nullable=False, server_default=str(default)))


def _drop(table, names):
    with op.batch_alter_table(table) as batch:
        for name in names:
            batch.drop_column(name)


def upgrade():
    _add("site_pages", (("hero_width", 0), ("hero_height", 0), ("hero_radius", 24)))
    _add("offerings", (("image_width", 0), ("image_height", 0), ("image_radius", 24)))
    _add("articles", (("image_width", 0), ("image_height", 0), ("image_radius", 24)))
    _add(
        "case_studies",
        (
            ("image_width", 0),
            ("image_height", 0),
            ("image_radius", 24),
            ("arch_width", 0),
            ("arch_height", 0),
            ("arch_radius", 24),
        ),
    )


def downgrade():
    _drop("case_studies", ("arch_radius", "arch_height", "arch_width", "image_radius", "image_height", "image_width"))
    _drop("articles", ("image_radius", "image_height", "image_width"))
    _drop("offerings", ("image_radius", "image_height", "image_width"))
    _drop("site_pages", ("hero_radius", "hero_height", "hero_width"))
