from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_user, logout_user

from app.extensions import db, limiter
from app.models import Article, CaseStudy, Category, ContactSubmission, Job, JobApplication, PageSeo, User
from app.services import admin_required, slugify

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _is_local_path(destination):
    if not destination.startswith("/") or destination.startswith("//") or destination.startswith("/\\"):
        return False
    if "\\" in destination or destination.startswith("/\t"):
        return False
    return True


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated and current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    error = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, role="admin").first()
        if user is None or not user.check_password(password) or not user.is_active:
            error = "Invalid email or password."
        else:
            login_user(user)
            destination = request.args.get("next") or ""
            if not _is_local_path(destination):
                destination = url_for("admin.dashboard")
            return redirect(destination)
    return render_template("admin/login.html", error=error)


@bp.route("/logout", methods=["POST"])
@admin_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


@bp.route("")
@admin_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        counts={
            "articles": Article.query.count(),
            "studies": CaseStudy.query.count(),
            "jobs": Job.query.count(),
            "applications": JobApplication.query.count(),
            "contacts": ContactSubmission.query.filter_by(status="new").count(),
        },
    )


@bp.route("/articles")
@admin_required
def articles():
    return render_template("admin/articles.html", articles=Article.query.order_by(Article.updated_at.desc()).all())


@bp.route("/articles/new", methods=["GET", "POST"])
@bp.route("/articles/<int:item_id>", methods=["GET", "POST"])
@admin_required
def article_edit(item_id=None):
    item = Article() if item_id is None else db.session.get(Article, item_id)
    if item is None:
        abort(404)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.slug = slugify(request.form.get("slug") or item.title)
        item.excerpt = request.form.get("excerpt", "").strip()
        item.content = request.form.get("content", "").strip()
        item.author = request.form.get("author", "").strip() or "Neural Xpert"
        item.featured_image = request.form.get("featured_image", "").strip()
        item.status = request.form.get("status", "draft")
        item.featured = request.form.get("featured") == "on"
        item.seo_title = request.form.get("seo_title", "").strip()
        item.meta_description = request.form.get("meta_description", "").strip()
        item.og_image = request.form.get("og_image", "").strip()
        category_id = request.form.get("category_id", type=int)
        item.category_id = category_id or None
        if item.status == "published" and item.published_at is None:
            item.published_at = datetime.now(timezone.utc)
        if not item.title or not item.slug:
            flash("Title is required.", "error")
        else:
            if item_id is None:
                db.session.add(item)
            db.session.commit()
            return redirect(url_for("admin.articles"))
    categories = Category.query.filter_by(kind="article").order_by(Category.name).all()
    return render_template("admin/article_form.html", item=item, categories=categories)


@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        kind = request.form.get("kind", "article")
        if name:
            db.session.add(Category(name=name, slug=slugify(name), kind=kind))
            db.session.commit()
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())


@bp.route("/case-studies")
@admin_required
def case_studies():
    return render_template("admin/case_studies.html", studies=CaseStudy.query.order_by(CaseStudy.updated_at.desc()).all())


@bp.route("/case-studies/new", methods=["GET", "POST"])
@bp.route("/case-studies/<int:item_id>", methods=["GET", "POST"])
@admin_required
def case_study_edit(item_id=None):
    item = CaseStudy() if item_id is None else db.session.get(CaseStudy, item_id)
    if item is None:
        abort(404)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.slug = slugify(request.form.get("slug") or item.title)
        item.category = request.form.get("category", "").strip()
        item.summary = request.form.get("summary", "").strip()
        item.content = request.form.get("content", "").strip()
        item.technologies = request.form.get("technologies", "").strip()
        item.featured_image = request.form.get("featured_image", "").strip()
        item.client_name = request.form.get("client_name", "").strip()
        item.client_display_name = request.form.get("client_display_name", "").strip()
        item.industry = request.form.get("industry", "").strip()
        item.challenge = request.form.get("challenge", "").strip()
        item.solution = request.form.get("solution", "").strip()
        item.architecture = request.form.get("architecture", "").strip()
        item.results = request.form.get("results", "").strip()
        item.status = request.form.get("status", "draft")
        item.seo_title = request.form.get("seo_title", "").strip()
        item.meta_description = request.form.get("meta_description", "").strip()
        if item.status == "published" and item.published_at is None:
            item.published_at = datetime.now(timezone.utc)
        if not item.title or not item.slug:
            flash("Title is required.", "error")
        else:
            if item_id is None:
                db.session.add(item)
            db.session.commit()
            return redirect(url_for("admin.case_studies"))
    return render_template("admin/case_study_form.html", item=item)


@bp.route("/jobs")
@admin_required
def jobs():
    return render_template("admin/jobs.html", jobs=Job.query.order_by(Job.updated_at.desc()).all())


@bp.route("/jobs/new", methods=["GET", "POST"])
@bp.route("/jobs/<int:item_id>", methods=["GET", "POST"])
@admin_required
def job_edit(item_id=None):
    item = Job() if item_id is None else db.session.get(Job, item_id)
    if item is None:
        abort(404)
    if request.method == "POST":
        item.title = request.form.get("title", "").strip()
        item.slug = slugify(request.form.get("slug") or item.title)
        item.department = request.form.get("department", "").strip()
        item.location = request.form.get("location", "").strip()
        item.employment_type = request.form.get("employment_type", "").strip()
        item.description = request.form.get("description", "").strip()
        item.requirements = request.form.get("requirements", "").strip()
        item.status = request.form.get("status", "draft")
        if item.status == "published" and item.published_at is None:
            item.published_at = datetime.now(timezone.utc)
        if not item.title or not item.slug:
            flash("Title is required.", "error")
        else:
            if item_id is None:
                db.session.add(item)
            db.session.commit()
            return redirect(url_for("admin.jobs"))
    return render_template("admin/job_form.html", item=item)


@bp.route("/applications")
@admin_required
def applications():
    rows = JobApplication.query.order_by(JobApplication.created_at.desc()).all()
    return render_template("admin/applications.html", applications=rows)


@bp.route("/applications/<int:item_id>/cv")
@admin_required
def application_cv(item_id):
    item = db.session.get(JobApplication, item_id)
    if item is None:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        item.cv_filename,
        as_attachment=True,
        download_name=item.cv_original_name or item.cv_filename,
    )


@bp.route("/contacts")
@admin_required
def contacts():
    return render_template(
        "admin/contacts.html",
        submissions=ContactSubmission.query.order_by(ContactSubmission.created_at.desc()).all(),
    )


@bp.route("/contacts/<int:item_id>/status", methods=["POST"])
@admin_required
def contact_status(item_id):
    item = db.session.get(ContactSubmission, item_id)
    if item is None:
        abort(404)
    item.status = request.form.get("status", "reviewed")
    db.session.commit()
    return redirect(url_for("admin.contacts"))


@bp.route("/seo", methods=["GET", "POST"])
@admin_required
def seo():
    if request.method == "POST":
        page_key = request.form.get("page_key", "").strip()
        record = PageSeo.query.filter_by(page_key=page_key).first() or PageSeo(page_key=page_key)
        record.seo_title = request.form.get("seo_title", "").strip()
        record.meta_description = request.form.get("meta_description", "").strip()
        record.og_image = request.form.get("og_image", "").strip()
        db.session.add(record)
        db.session.commit()
        return redirect(url_for("admin.seo"))
    return render_template("admin/seo.html", records=PageSeo.query.order_by(PageSeo.page_key).all())
