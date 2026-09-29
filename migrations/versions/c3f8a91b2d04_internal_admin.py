"""Internal admin, visitor counts, and inquiry notes

Revision ID: c3f8a91b2d04
Revises: 62ab33428bea
Create Date: 2026-09-29 10:20:00

"""
from alembic import op
import sqlalchemy as sa


revision = "c3f8a91b2d04"
down_revision = "62ab33428bea"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("articles", sa.Column("managed_in_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("case_studies", sa.Column("managed_in_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("contact_submissions", sa.Column("notes", sa.Text(), nullable=False, server_default=""))
    op.create_table(
        "staff_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("totp_secret", sa.String(length=64), nullable=False),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_totp_step", sa.Integer(), nullable=False),
        sa.Column("recovery_hashes", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_users_email", "staff_users", ["email"], unique=True)
    op.create_table(
        "login_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_challenges_staff_id", "login_challenges", ["staff_id"])
    op.create_table(
        "daily_page_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "path", name="uq_daily_page_path"),
    )
    op.create_index("ix_daily_page_views_day", "daily_page_views", ["day"])
    op.create_table(
        "daily_visitors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "visitor_hash", name="uq_daily_visitor"),
    )
    op.create_index("ix_daily_visitors_day", "daily_visitors", ["day"])


def downgrade():
    op.drop_index("ix_daily_visitors_day", table_name="daily_visitors")
    op.drop_table("daily_visitors")
    op.drop_index("ix_daily_page_views_day", table_name="daily_page_views")
    op.drop_table("daily_page_views")
    op.drop_index("ix_login_challenges_staff_id", table_name="login_challenges")
    op.drop_table("login_challenges")
    op.drop_index("ix_staff_users_email", table_name="staff_users")
    op.drop_table("staff_users")
    op.drop_column("contact_submissions", "notes")
    op.drop_column("case_studies", "managed_in_admin")
    op.drop_column("articles", "managed_in_admin")
