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
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    og_image = db.Column(db.String(500), nullable=False, default="")

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
    published_at = db.Column(db.DateTime(timezone=True))
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
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
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class PageSeo(db.Model):
    __tablename__ = "page_seo"

    id = db.Column(db.Integer, primary_key=True)
    page_key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    seo_title = db.Column(db.String(255), nullable=False, default="")
    meta_description = db.Column(db.String(320), nullable=False, default="")
    og_image = db.Column(db.String(500), nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
