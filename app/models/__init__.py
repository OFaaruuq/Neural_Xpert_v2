from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(32), nullable=False, default="article")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    excerpt = db.Column(db.Text, nullable=False, default="")
    content = db.Column(db.Text, nullable=False, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    featured_image = db.Column(db.String(500), nullable=False, default="")
    author = db.Column(db.String(120), nullable=False, default="Neural Xpert")
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    managed_in_admin = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    og_image = db.Column(db.String(500), nullable=False, default="")
    tags = db.Column(db.String(500), nullable=False, default="")
    focus_keyword = db.Column(db.String(160), nullable=False, default="")
    canonical_url = db.Column(db.String(500), nullable=False, default="")
    robots = db.Column(db.String(80), nullable=False, default="")
    cta_label = db.Column(db.String(120), nullable=False, default="")
    cta_url = db.Column(db.String(500), nullable=False, default="")
    blocks = db.Column(db.Text, nullable=False, default="")

    category = db.relationship("Category")


class CaseStudy(db.Model):
    __tablename__ = "case_studies"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    category = db.Column(db.String(120), nullable=False, default="")
    summary = db.Column(db.Text, nullable=False, default="")
    content = db.Column(db.Text, nullable=False, default="")
    technologies = db.Column(db.String(500), nullable=False, default="")
    featured_image = db.Column(db.String(500), nullable=False, default="")
    client_name = db.Column(db.String(255), nullable=False, default="")
    client_display_name = db.Column(db.String(255), nullable=False, default="")
    industry = db.Column(db.String(120), nullable=False, default="")
    challenge = db.Column(db.Text, nullable=False, default="")
    solution = db.Column(db.Text, nullable=False, default="")
    architecture = db.Column(db.Text, nullable=False, default="")
    results = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    managed_in_admin = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime(timezone=True))
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    customer_quote = db.Column(db.Text, nullable=False, default="")
    metrics = db.Column(db.Text, nullable=False, default="")
    metrics_verified = db.Column(db.Boolean, nullable=False, default=False)
    cloud_platform = db.Column(db.String(255), nullable=False, default="")
    data_sources = db.Column(db.Text, nullable=False, default="")
    integrations = db.Column(db.Text, nullable=False, default="")
    security_controls = db.Column(db.Text, nullable=False, default="")
    implementation = db.Column(db.Text, nullable=False, default="")
    architecture_image = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    def technology_list(self):
        return [item.strip() for item in (self.technologies or "").split(",") if item.strip()]


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    department = db.Column(db.String(120), nullable=False, default="")
    location = db.Column(db.String(120), nullable=False, default="")
    employment_type = db.Column(db.String(80), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    requirements = db.Column(db.Text, nullable=False, default="")
    responsibilities = db.Column(db.Text, nullable=False, default="")
    experience = db.Column(db.Text, nullable=False, default="")
    workplace = db.Column(db.String(40), nullable=False, default="")
    closing_on = db.Column(db.Date)
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    applications = db.relationship("JobApplication", back_populates="job")


class JobApplication(db.Model):
    __tablename__ = "job_applications"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=False, default="")
    cover_letter = db.Column(db.Text, nullable=False, default="")
    cv_filename = db.Column(db.String(255), nullable=False)
    cv_original_name = db.Column(db.String(255), nullable=False, default="")
    linkedin = db.Column(db.String(500), nullable=False, default="")
    status = db.Column(db.String(32), nullable=False, default="new", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    job = db.relationship("Job", back_populates="applications")


class ContactSubmission(db.Model):
    __tablename__ = "contact_submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(160), nullable=False, default="")
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=False, default="")
    subject = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="new", index=True)
    notes = db.Column(db.Text, nullable=False, default="")
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"))
    job_title = db.Column(db.String(160), nullable=False, default="")
    country = db.Column(db.String(80), nullable=False, default="")
    interest = db.Column(db.String(160), nullable=False, default="")
    source_page = db.Column(db.String(300), nullable=False, default="")
    utm_source = db.Column(db.String(160), nullable=False, default="")
    follow_up_on = db.Column(db.Date)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    assigned_to = db.relationship("StaffUser")


class PageSeo(db.Model):
    __tablename__ = "page_seo"

    id = db.Column(db.Integer, primary_key=True)
    page_key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    og_image = db.Column(db.String(500), nullable=False, default="")
    og_title = db.Column(db.String(255), nullable=False, default="")
    og_description = db.Column(db.String(320), nullable=False, default="")
    twitter_title = db.Column(db.String(255), nullable=False, default="")
    twitter_description = db.Column(db.String(320), nullable=False, default="")
    canonical_url = db.Column(db.String(500), nullable=False, default="")
    focus_keyword = db.Column(db.String(160), nullable=False, default="")
    robots = db.Column(db.String(80), nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class StaffRole(db.Model):
    __tablename__ = "staff_roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    permissions = db.Column(db.Text, nullable=False, default="")
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    users = db.relationship("StaffUser", back_populates="role")

    def permission_set(self):
        return {item.strip() for item in (self.permissions or "").split(",") if item.strip()}


class StaffUser(db.Model):
    __tablename__ = "staff_users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, default="")
    role_id = db.Column(db.Integer, db.ForeignKey("staff_roles.id"), index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.relationship("StaffRole", back_populates="users")

    @property
    def display_name(self):
        return self.name or self.email

    def permission_set(self):
        if self.role is None:
            return set()
        return self.role.permission_set()

    def has_any(self, codes):
        owned = self.permission_set()
        return any(code in owned for code in codes)
    totp_secret = db.Column(db.String(64), nullable=False, default="")
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    last_totp_step = db.Column(db.Integer, nullable=False, default=0)
    recovery_hashes = db.Column(db.Text, nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class LoginChallenge(db.Model):
    __tablename__ = "login_challenges"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff_users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    staff = db.relationship("StaffUser")


class DailyPageView(db.Model):
    __tablename__ = "daily_page_views"
    __table_args__ = (db.UniqueConstraint("day", "path", name="uq_daily_page_path"),)

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, index=True)
    path = db.Column(db.String(300), nullable=False)
    views = db.Column(db.Integer, nullable=False, default=0)


class DailyVisitor(db.Model):
    __tablename__ = "daily_visitors"
    __table_args__ = (db.UniqueConstraint("day", "visitor_hash", name="uq_daily_visitor"),)

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, index=True)
    visitor_hash = db.Column(db.String(64), nullable=False)


from app.models.platform import (  # noqa: E402,F401
    AuditLog,
    ContentRevision,
    ConversionEvent,
    Credential,
    HomeSection,
    MediaAsset,
    NavItem,
    Offering,
    Partner,
    RedirectRule,
    SitePage,
    SiteSetting,
    Testimonial,
)
