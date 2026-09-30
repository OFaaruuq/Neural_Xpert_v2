"""Widen authenticator secrets and add shared rate limits

Revision ID: a91c4e2b7d10
Revises: f6a1d8e04c27
Create Date: 2026-09-30 09:40:00

"""
import sqlalchemy as sa
from alembic import op


revision = "a91c4e2b7d10"
down_revision = "f6a1d8e04c27"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("staff_users") as batch:
        batch.alter_column(
            "totp_secret",
            existing_type=sa.String(length=64),
            type_=sa.Text(),
            existing_nullable=False,
        )
    op.create_table(
        "request_rates",
        sa.Column("bucket", sa.String(length=180), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("request_rates")
    with op.batch_alter_table("staff_users") as batch:
        batch.alter_column(
            "totp_secret",
            existing_type=sa.Text(),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
