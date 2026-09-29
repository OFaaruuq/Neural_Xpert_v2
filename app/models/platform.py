from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class SitePage(db.Model):
    __tablename__ = "site_pages"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(160), nullable=False, default="")
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    hero_title = db.Column(db.String(255), nullable=False, default="")
    hero_subtitle = db.Column(db.Text, nullable=False, default="")
    hero_image = db.Column(db.String(500), nullable=False, default="")
    summary = db.Column(db.Text, nullable=False, default="")
    cta_label = db.Column(db.String(120), nullable=False, default="")
    cta_url = db.Column(db.String(500), nullable=False, default="")
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    focus_keyword = db.Column(db.String(160), nullable=False, default="")
    canonical_url = db.Column(db.String(500), nullable=False, default="")
    og_title = db.Column(db.String(255), nullable=False, default="")
    og_description = db.Column(db.String(320), nullable=False, default="")
    og_image = db.Column(db.String(500), nullable=False, default="")
    robots = db.Column(db.String(80), nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class HomeSection(db.Model):
    __tablename__ = "home_sections"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    eyebrow = db.Column(db.String(160), nullable=False, default="")
    headline = db.Column(db.String(255), nullable=False, default="")
    summary = db.Column(db.Text, nullable=False, default="")
    cta_label = db.Column(db.String(120), nullable=False, default="")
    cta_url = db.Column(db.String(500), nullable=False, default="")


class Offering(db.Model):
    __tablename__ = "offerings"
    __table_args__ = (db.UniqueConstraint("kind", "slug", name="uq_offering_kind_slug"),)

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(32), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(160), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False, default="")
    body = db.Column(db.Text, nullable=False, default="")
    hero_image = db.Column(db.String(500), nullable=False, default="")
    icon = db.Column(db.String(500), nullable=False, default="")
    challenges = db.Column(db.Text, nullable=False, default="")
    capabilities = db.Column(db.Text, nullable=False, default="")
    architecture = db.Column(db.Text, nullable=False, default="")
    benefits = db.Column(db.Text, nullable=False, default="")
    use_cases = db.Column(db.Text, nullable=False, default="")
    cta_label = db.Column(db.String(120), nullable=False, default="")
    cta_url = db.Column(db.String(500), nullable=False, default="")
    featured = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    focus_keyword = db.Column(db.String(160), nullable=False, default="")
    published_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False, default="")
    alt_text = db.Column(db.String(255), nullable=False, default="")
    title = db.Column(db.String(255), nullable=False, default="")
    folder = db.Column(db.String(80), nullable=False, default="general")
    width = db.Column(db.Integer, nullable=False, default=0)
    height = db.Column(db.Integer, nullable=False, default=0)
    size = db.Column(db.Integer, nullable=False, default=0)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    uploaded_by = db.relationship("StaffUser")


class NavItem(db.Model):
    __tablename__ = "nav_items"

    id = db.Column(db.Integer, primary_key=True)
    menu = db.Column(db.String(32), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(500), nullable=False, default="/")
    position = db.Column(db.Integer, nullable=False, default=0)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    new_tab = db.Column(db.Boolean, nullable=False, default=False)


class Partner(db.Model):
    __tablename__ = "partners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    logo = db.Column(db.String(500), nullable=False, default="")
    relationship = db.Column(db.String(80), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    website = db.Column(db.String(500), nullable=False, default="")
    display = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    evidence = db.Column(db.Text, nullable=False, default="")


class Credential(db.Model):
    __tablename__ = "credentials"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    issuer = db.Column(db.String(160), nullable=False, default="")
    holder = db.Column(db.String(160), nullable=False, default="")
    issued_on = db.Column(db.Date)
    expires_on = db.Column(db.Date)
    credential_url = db.Column(db.String(500), nullable=False, default="")
    badge = db.Column(db.String(500), nullable=False, default="")
    status = db.Column(db.String(32), nullable=False, default="active")
    display = db.Column(db.Boolean, nullable=False, default=False)


class Testimonial(db.Model):
    __tablename__ = "testimonials"

    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(160), nullable=False)
    company = db.Column(db.String(160), nullable=False, default="")
    role = db.Column(db.String(160), nullable=False, default="")
    quote = db.Column(db.Text, nullable=False, default="")
    image = db.Column(db.String(500), nullable=False, default="")
    case_study_id = db.Column(db.Integer, db.ForeignKey("case_studies.id"))
    approved = db.Column(db.Boolean, nullable=False, default=False)
    evidence = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(32), nullable=False, default="draft")

    case_study = db.relationship("CaseStudy")


class SiteSetting(db.Model):
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default="")


class ContentRevision(db.Model):
    __tablename__ = "content_revisions"

    id = db.Column(db.Integer, primary_key=True)
    object_type = db.Column(db.String(40), nullable=False, index=True)
    object_id = db.Column(db.Integer, nullable=False, index=True)
    note = db.Column(db.String(255), nullable=False, default="")
    snapshot = db.Column(db.Text, nullable=False, default="")
    staff_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    staff = db.relationship("StaffUser")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"))
    action = db.Column(db.String(80), nullable=False)
    object_type = db.Column(db.String(40), nullable=False, default="")
    object_id = db.Column(db.String(40), nullable=False, default="")
    detail = db.Column(db.Text, nullable=False, default="")
    ip_address = db.Column(db.String(64), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    staff = db.relationship("StaffUser")


class ConversionEvent(db.Model):
    __tablename__ = "conversion_events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, index=True)
    path = db.Column(db.String(300), nullable=False, default="")
    label = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class RedirectRule(db.Model):
    __tablename__ = "redirect_rules"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(300), unique=True, nullable=False)
    target = db.Column(db.String(500), nullable=False)
    status_code = db.Column(db.Integer, nullable=False, default=301)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
