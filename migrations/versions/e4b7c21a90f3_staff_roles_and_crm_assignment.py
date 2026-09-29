"""Staff roles, permissions, and CRM assignment

Revision ID: e4b7c21a90f3
Revises: c3f8a91b2d04
Create Date: 2026-09-29 11:20:00

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "e4b7c21a90f3"
down_revision = "c3f8a91b2d04"
branch_labels = None
depends_on = None

ROLES = (
    ("administrator", "Administrator", "overview,crm.view,crm.edit,content.view,content.edit,careers.view,careers.edit,users.manage,roles.manage", True),
    ("crm", "CRM", "overview,crm.view,crm.edit", False),
    ("editor", "Editor", "overview,content.view,content.edit,careers.view,careers.edit", False),
    ("viewer", "Viewer", "overview,crm.view,content.view,careers.view", False),
)


def upgrade():
    op.create_table(
        "staff_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("permissions", sa.Text(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_roles_slug", "staff_roles", ["slug"], unique=True)
    roles = sa.table(
        "staff_roles",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("permissions", sa.Text),
        sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        roles,
        [
            {
                "name": name,
                "slug": slug,
                "permissions": permissions,
                "is_system": system,
                "created_at": now,
            }
            for slug, name, permissions, system in ROLES
        ],
    )
    with op.batch_alter_table("staff_users") as batch:
        batch.add_column(sa.Column("name", sa.String(length=120), nullable=False, server_default=""))
        batch.add_column(sa.Column("role_id", sa.Integer(), nullable=True))
        batch.create_index("ix_staff_users_role_id", ["role_id"])
        batch.create_foreign_key("fk_staff_users_role_id", "staff_roles", ["role_id"], ["id"])
    bind = op.get_bind()
    admin_id = bind.execute(sa.text("SELECT id FROM staff_roles WHERE slug = 'administrator'")).scalar()
    bind.execute(sa.text("UPDATE staff_users SET role_id = :role_id WHERE role_id IS NULL"), {"role_id": admin_id})
    with op.batch_alter_table("contact_submissions") as batch:
        batch.add_column(sa.Column("assigned_to_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_contact_submissions_assigned_to_id", "staff_users", ["assigned_to_id"], ["id"])


def downgrade():
    with op.batch_alter_table("contact_submissions") as batch:
        batch.drop_constraint("fk_contact_submissions_assigned_to_id", type_="foreignkey")
        batch.drop_column("assigned_to_id")
    with op.batch_alter_table("staff_users") as batch:
        batch.drop_constraint("fk_staff_users_role_id", type_="foreignkey")
        batch.drop_index("ix_staff_users_role_id")
        batch.drop_column("role_id")
        batch.drop_column("name")
    op.drop_index("ix_staff_roles_slug", table_name="staff_roles")
    op.drop_table("staff_roles")
