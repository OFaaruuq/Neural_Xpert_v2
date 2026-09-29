"""Website operations: pages, offerings, leads, SEO, governance

Revision ID: f6a1d8e04c27
Revises: e4b7c21a90f3
Create Date: 2026-09-29 12:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "f6a1d8e04c27"
down_revision = "e4b7c21a90f3"
branch_labels = None
depends_on = None


def _add(table, columns):
    with op.batch_alter_table(table) as batch:
        for column in columns:
            batch.add_column(column)


def upgrade():
    _add("articles", [
        sa.Column("tags", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("focus_keyword", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("canonical_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("robots", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("cta_label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("cta_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("blocks", sa.Text(), nullable=False, server_default=""),
    ])
    _add("case_studies", [
        sa.Column("customer_quote", sa.Text(), nullable=False, server_default=""),
        sa.Column("metrics", sa.Text(), nullable=False, server_default=""),
        sa.Column("metrics_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cloud_platform", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("data_sources", sa.Text(), nullable=False, server_default=""),
        sa.Column("integrations", sa.Text(), nullable=False, server_default=""),
        sa.Column("security_controls", sa.Text(), nullable=False, server_default=""),
        sa.Column("implementation", sa.Text(), nullable=False, server_default=""),
        sa.Column("architecture_image", sa.String(length=500), nullable=False, server_default=""),
    ])
    _add("jobs", [
        sa.Column("responsibilities", sa.Text(), nullable=False, server_default=""),
        sa.Column("experience", sa.Text(), nullable=False, server_default=""),
        sa.Column("workplace", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("closing_on", sa.Date(), nullable=True),
    ])
    _add("job_applications", [
        sa.Column("linkedin", sa.String(length=500), nullable=False, server_default=""),
    ])
    _add("contact_submissions", [
        sa.Column("job_title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("country", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("interest", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("source_page", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("utm_source", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("follow_up_on", sa.Date(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    ])
    _add("page_seo", [
        sa.Column("og_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("og_description", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("twitter_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("twitter_description", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("canonical_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("focus_keyword", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("robots", sa.String(length=80), nullable=False, server_default=""),
    ])
    op.create_table(
        "site_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("hero_title", sa.String(length=255), nullable=False),
        sa.Column("hero_subtitle", sa.Text(), nullable=False),
        sa.Column("hero_image", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.String(length=120), nullable=False),
        sa.Column("cta_url", sa.String(length=500), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=False),
        sa.Column("meta_description", sa.String(length=320), nullable=False),
        sa.Column("focus_keyword", sa.String(length=160), nullable=False),
        sa.Column("canonical_url", sa.String(length=500), nullable=False),
        sa.Column("og_title", sa.String(length=255), nullable=False),
        sa.Column("og_description", sa.String(length=320), nullable=False),
        sa.Column("og_image", sa.String(length=500), nullable=False),
        sa.Column("robots", sa.String(length=80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_pages_key", "site_pages", ["key"], unique=True)
    op.create_table(
        "home_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("eyebrow", sa.String(length=160), nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.String(length=120), nullable=False),
        sa.Column("cta_url", sa.String(length=500), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_home_sections_key", "home_sections", ["key"], unique=True)
    op.create_table(
        "offerings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("hero_image", sa.String(length=500), nullable=False),
        sa.Column("icon", sa.String(length=500), nullable=False),
        sa.Column("challenges", sa.Text(), nullable=False),
        sa.Column("capabilities", sa.Text(), nullable=False),
        sa.Column("architecture", sa.Text(), nullable=False),
        sa.Column("benefits", sa.Text(), nullable=False),
        sa.Column("use_cases", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.String(length=120), nullable=False),
        sa.Column("cta_url", sa.String(length=500), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=False),
        sa.Column("meta_description", sa.String(length=320), nullable=False),
        sa.Column("focus_keyword", sa.String(length=160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "slug", name="uq_offering_kind_slug"),
    )
    op.create_index("ix_offerings_kind", "offerings", ["kind"])
    op.create_index("ix_offerings_slug", "offerings", ["slug"])
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("folder", sa.String(length=80), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["staff_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "nav_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("menu", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("new_tab", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nav_items_menu", "nav_items", ["menu"])
    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("logo", sa.String(length=500), nullable=False),
        sa.Column("relationship", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=False),
        sa.Column("display", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("issuer", sa.String(length=160), nullable=False),
        sa.Column("holder", sa.String(length=160), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("credential_url", sa.String(length=500), nullable=False),
        sa.Column("badge", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "testimonials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer", sa.String(length=160), nullable=False),
        sa.Column("company", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("image", sa.String(length=500), nullable=False),
        sa.Column("case_study_id", sa.Integer(), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["case_study_id"], ["case_studies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_settings_key", "site_settings", ["key"], unique=True)
    op.create_table(
        "content_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_revisions_object_type", "content_revisions", ["object_type"])
    op.create_index("ix_content_revisions_object_id", "content_revisions", ["object_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_id", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conversion_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversion_events_name", "conversion_events", ["name"])
    op.create_table(
        "redirect_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=False),
        sa.Column("target", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_redirect_rules_source", "redirect_rules", ["source"], unique=True)


def downgrade():
    op.drop_index("ix_redirect_rules_source", table_name="redirect_rules")
    op.drop_table("redirect_rules")
    op.drop_index("ix_conversion_events_name", table_name="conversion_events")
    op.drop_table("conversion_events")
    op.drop_table("audit_logs")
    op.drop_index("ix_content_revisions_object_id", table_name="content_revisions")
    op.drop_index("ix_content_revisions_object_type", table_name="content_revisions")
    op.drop_table("content_revisions")
    op.drop_index("ix_site_settings_key", table_name="site_settings")
    op.drop_table("site_settings")
    op.drop_table("testimonials")
    op.drop_table("credentials")
    op.drop_table("partners")
    op.drop_index("ix_nav_items_menu", table_name="nav_items")
    op.drop_table("nav_items")
    op.drop_table("media_assets")
    op.drop_index("ix_offerings_slug", table_name="offerings")
    op.drop_index("ix_offerings_kind", table_name="offerings")
    op.drop_table("offerings")
    op.drop_index("ix_home_sections_key", table_name="home_sections")
    op.drop_table("home_sections")
    op.drop_index("ix_site_pages_key", table_name="site_pages")
    op.drop_table("site_pages")
