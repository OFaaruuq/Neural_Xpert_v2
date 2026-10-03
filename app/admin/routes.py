import os
from datetime import date
from functools import wraps

import segno
from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, session, url_for

from app.admin.access import PERMISSIONS, ensure_roles, ensure_staff_role
from app.admin.catalog import record_audit, record_security
from app.admin.security import (
    CODE_ERROR,
    LOGIN_ERROR,
    account_is_locked,
    begin_enrollment,
    check_email_code,
    check_password,
    complete_login,
    confirm_enrollment,
    ensure_totp_sealed,
    session_is_fresh,
    consume_recovery_code,
    current_staff,
    normalize_email,
    pending_login,
    provisioning_uri,
    register_failure,
    session_stamp,
    start_email_otp,
    utcnow,
    verify_totp,
)
from app.extensions import db, limiter
from app.limits import rate_limited
from app.models import (
    Article,
    CaseStudy,
    Category,
    ContactSubmission,
    Job,
    JobApplication,
    StaffRole,
    StaffUser,
)
from app.case_style import FONT_CHOICES, apply_card_type, apply_page_style
from app.images import apply_managed_image, save_public_image
from app.services import safe_static_path, safe_url, sanitize_html, slugify
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.after_request
def _admin_not_cached(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response

INQUIRY_STATUSES = ("new", "contacted", "qualified", "opportunity", "proposal", "won", "lost", "in progress", "closed")
APPLICATION_STATUSES = ("new", "screening", "interview", "offer", "hired", "rejected", "reviewing", "closed")
CONTENT_STATUSES = ("draft", "published")
ARTICLE_STATUSES = ("draft", "review", "scheduled", "published", "archived")
JOB_STATUSES = ("draft", "open", "published", "closed")


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        staff = current_staff()
        if staff is None or not session_is_fresh():
            return redirect(url_for("admin.login"))
        ensure_staff_role(staff)
        g.staff = staff
        return view(*args, **kwargs)

    return wrapped


def permission_required(*codes):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            staff = current_staff()
            if staff is None or not session_is_fresh():
                return redirect(url_for("admin.login"))
            ensure_staff_role(staff)
            g.staff = staff
            if not staff.has_any(codes):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.errorhandler(403)
def forbidden(_error):
    if current_staff() is None:
        return redirect(url_for("admin.login"))
    ensure_staff_role(current_staff())
    g.staff = current_staff()
    return _render("admin/forbidden.html", title="Access denied"), 403


def _render(template, **context):
    context.setdefault("title", "Admin")
    return render_template(template, **context)


def _unique_slug(model, source, current_id=None):
    base = slugify(source) or "item"
    slug = base
    number = 2
    while True:
        existing = model.query.filter_by(slug=slug).first()
        if existing is None or existing.id == current_id:
            return slug
        slug = f"{base}-{number}"[:200]
        number += 1


@bp.route("/")
@permission_required("overview")
def dashboard():
    from app.admin.catalog import ensure_catalog
    from app.admin.overview import load_board

    ensure_catalog()
    ask = None
    if g.staff.has_any(("settings.manage",)):
        from app.ai_support import admin_state

        ask = admin_state()
    return _render("admin/dashboard.html", title="Dashboard", board=load_board(), ask=ask)


def _mask_email(email):
    name, _, domain = (email or "").partition("@")
    if not name or not domain:
        return email or ""
    visible = name[:2] if len(name) > 2 else name[:1]
    return f"{visible}{'•' * max(1, len(name) - len(visible))}@{domain}"


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute", methods=["POST"])
def login():
    if current_staff():
        return redirect(url_for("admin.dashboard"))
    error = ""
    entered = (request.form.get("email") or "").strip() if request.method == "POST" else ""
    if request.method == "POST" and rate_limited("admin-login", 8, 60):
        return _render("admin/login.html", title="Sign in", error="Too many attempts. Try again in a minute.", email=entered), 429
    if request.method == "POST":
        email = normalize_email(entered)
        password = request.form.get("password") or ""
        staff = StaffUser.query.filter_by(email=email).first() if email else None
        locked = bool(staff and staff.is_active and account_is_locked(staff))
        if staff and staff.is_active:
            password_ok = check_password(staff, password)
        else:
            check_password(None, password)
            password_ok = False
        if not password_ok or locked:
            if staff and staff.is_active and not locked:
                register_failure(staff)
            record_security("login_failure", _mask_email(entered), staff if staff and staff.is_active else None)
            error = LOGIN_ERROR
        else:
            record_security("login_password_accepted", _mask_email(staff.email), staff)
            if start_email_otp(staff) is None:
                error = "The sign-in code could not be emailed. Try again in a moment."
            else:
                return redirect(url_for("admin.verify"))
    return _render("admin/login.html", title="Sign in", error=error, email=entered)


@bp.route("/verify", methods=["GET", "POST"])
@limiter.limit("8 per minute", methods=["POST"])
def verify():
    staff, challenge = pending_login()
    if staff is None:
        return redirect(url_for("admin.login"))
    error = ""
    if request.method == "POST" and rate_limited("admin-verify", 8, 60):
        error = "Too many attempts. Try again in a minute."
        return _render(
            "admin/verify.html",
            title="Verify sign-in",
            error=error,
            totp_enabled=staff.totp_enabled,
            inbox=_mask_email(staff.email),
            dev_code=session.get("login_dev_code", ""),
        ), 429
    if request.method == "POST":
        if not check_email_code(staff, challenge, request.form.get("email_code")):
            record_security("login_code_rejected", _mask_email(staff.email), staff)
            error = CODE_ERROR
        elif staff.totp_enabled and not (
            verify_totp(staff, request.form.get("totp_code"))
            or consume_recovery_code(staff, request.form.get("recovery_code"))
        ):
            challenge.attempts += 1
            if challenge.attempts >= 5:
                challenge.used = True
            db.session.commit()
            record_security("login_code_rejected", _mask_email(staff.email), staff)
            error = CODE_ERROR
        else:
            challenge.used = True
            db.session.commit()
            if staff.totp_enabled:
                complete_login(staff)
                record_security("login_success", _mask_email(staff.email), staff)
                return redirect(url_for("admin.dashboard"))
            begin_enrollment(staff)
            return redirect(url_for("admin.enroll"))
    return _render(
        "admin/verify.html",
        title="Verify sign-in",
        error=error,
        totp_enabled=staff.totp_enabled,
        inbox=_mask_email(staff.email),
        dev_code=session.get("login_dev_code", ""),
    )


@bp.route("/enroll", methods=["GET", "POST"])
@limiter.limit("8 per minute", methods=["POST"])
def enroll():
    enroll_id = session.get("enroll_staff_id")
    staff = db.session.get(StaffUser, enroll_id) if enroll_id else None
    if staff is None or not staff.is_active:
        return redirect(url_for("admin.login"))
    error = ""
    status = 200
    ensure_totp_sealed(staff)
    if request.method == "POST" and rate_limited("admin-enroll", 8, 60):
        error = "Too many attempts. Try again in a minute."
        status = 429
    elif request.method == "POST":
        if int(session.get("enroll_attempts") or 0) >= 5:
            session.clear()
            return redirect(url_for("admin.login"))
        if confirm_enrollment(staff, request.form.get("totp_code")):
            return redirect(url_for("admin.recovery"))
        session["enroll_attempts"] = int(session.get("enroll_attempts") or 0) + 1
        record_security("authenticator_rejected", _mask_email(staff.email), staff)
        error = CODE_ERROR
    qr = segno.make(provisioning_uri(staff), error="m").svg_data_uri(scale=4)
    return _render(
        "admin/enroll.html",
        title="Set up authenticator",
        error=error,
        qr=qr,
        secret=staff.totp_secret,
    ), status


@bp.route("/recovery", methods=["GET", "POST"])
def recovery():
    enroll_id = session.get("enroll_staff_id")
    staff = db.session.get(StaffUser, enroll_id) if enroll_id else None
    codes = session.get("recovery_codes") or []
    if staff is None or not codes:
        return redirect(url_for("admin.login"))
    if request.method == "POST":
        session.pop("recovery_codes", None)
        complete_login(staff)
        record_security("login_success", _mask_email(staff.email), staff)
        return redirect(url_for("admin.dashboard"))
    return _render("admin/recovery.html", title="Save recovery codes", codes=codes)


@bp.route("/logout", methods=["POST"])
def logout():
    staff = current_staff()
    if staff:
        record_security("logout", _mask_email(staff.email), staff)
    session.clear()
    return redirect(url_for("admin.login"))


@bp.route("/account", methods=["GET", "POST"])
@staff_required
def account():
    error = ""
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        if not check_password_hash(g.staff.password_hash, current):
            error = "Current password is incorrect."
        elif len(new_password) < 12:
            error = "Use at least 12 characters."
        elif not verify_totp(g.staff, request.form.get("totp_code")):
            error = CODE_ERROR
        else:
            g.staff.password_hash = generate_password_hash(new_password)
            db.session.commit()
            session["staff_stamp"] = session_stamp(g.staff)
            record_security("password_changed", _mask_email(g.staff.email), g.staff)
            flash("Password updated.")
            return redirect(url_for("admin.account"))
    return _render("admin/account.html", title="Account", error=error)


def _lead_staff():
    return StaffUser.query.filter_by(is_active=True).order_by(StaffUser.email).all()


def _apply_inquiry(row):
    status = request.form.get("status", "")
    if status in INQUIRY_STATUSES:
        row.status = status
    elif not row.status:
        row.status = "new"
    managed = request.form.get("manage") == "1"
    if managed:
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        subject = (request.form.get("subject") or "").strip()
        message = (request.form.get("message") or "").strip()
        if not name or not email or not subject or not message:
            return "Name, email, subject, and message are required."
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            return "Enter a valid email address."
        row.name = name[:120]
        row.company = (request.form.get("company") or "")[:160]
        row.email = email[:255]
        row.phone = (request.form.get("phone") or "")[:50]
        row.subject = subject[:160]
        row.message = message[:5000]
        row.job_title = (request.form.get("job_title") or "")[:160]
        row.country = (request.form.get("country") or "")[:80]
        row.interest = (request.form.get("interest") or "")[:160]
        row.utm_source = (request.form.get("utm_source") or "")[:160]
        row.source_page = (request.form.get("source_page") or "")[:300]
        row.notes = (request.form.get("notes") or "")[:5000]
        row.archived = request.form.get("archived") == "1"
        assignee = request.form.get("assigned_to_id", type=int)
        row.assigned_to = db.session.get(StaffUser, assignee) if assignee else None
        follow_up = (request.form.get("follow_up_on") or "").strip()
        if follow_up:
            try:
                row.follow_up_on = date.fromisoformat(follow_up)
            except ValueError:
                return "Enter a valid follow-up date."
        else:
            row.follow_up_on = None
    if not managed and "notes" in request.form:
        row.notes = (request.form.get("notes") or "")[:5000]
    return ""


@bp.route("/crm")
@permission_required("crm.view")
def crm():
    status = request.args.get("status", "")
    if status not in INQUIRY_STATUSES:
        status = ""
    search = (request.args.get("q") or "").strip()
    archived = request.args.get("archived") == "1"
    owner = request.args.get("owner", type=int)
    due = request.args.get("due") == "1"
    query = ContactSubmission.query.filter_by(archived=archived)
    if status:
        query = query.filter_by(status=status)
    if owner:
        query = query.filter_by(assigned_to_id=owner)
    if due:
        query = query.filter(ContactSubmission.follow_up_on.isnot(None), ContactSubmission.follow_up_on <= date.today())
    if search:
        like = f"%{search.replace('%', '').replace('_', '')}%"
        query = query.filter(
            ContactSubmission.name.ilike(like)
            | ContactSubmission.email.ilike(like)
            | ContactSubmission.company.ilike(like)
            | ContactSubmission.subject.ilike(like)
            | ContactSubmission.phone.ilike(like)
        )
    rows = query.order_by(ContactSubmission.created_at.desc()).all()
    active = ContactSubmission.query.filter_by(archived=False)
    counts = {item: active.filter(ContactSubmission.status == item).count() for item in INQUIRY_STATUSES}
    return _render(
        "admin/crm.html",
        title="CRM",
        rows=rows,
        status=status,
        search=search,
        statuses=INQUIRY_STATUSES,
        counts=counts,
        total=active.count(),
        active_total=active.count(),
        archived=archived,
        archived_count=ContactSubmission.query.filter_by(archived=True).count(),
        due=due,
        due_count=ContactSubmission.query.filter(
            ContactSubmission.archived.is_(False),
            ContactSubmission.follow_up_on.isnot(None),
            ContactSubmission.follow_up_on <= date.today(),
        ).count(),
        owner=owner or "",
        staff=_lead_staff(),
        today=date.today(),
    )


@bp.route("/crm/new", methods=["GET", "POST"])
@permission_required("crm.edit")
def crm_new():
    row = ContactSubmission(status="new", name="", email="", phone="", subject="", message="", notes="")
    error = ""
    if request.method == "POST":
        error = _apply_inquiry(row)
        if not error:
            db.session.add(row)
            db.session.flush()
            record_audit("create", "lead", row.id, row.email)
            db.session.commit()
            flash("Lead added.")
            return redirect(url_for("admin.inquiry", inquiry_id=row.id))
    return _render("admin/inquiry.html", title="New lead", row=row, statuses=INQUIRY_STATUSES, staff=_lead_staff(), error=error, today=date.today())


@bp.route("/inquiries")
@permission_required("crm.view")
def inquiries():
    status = request.args.get("status", "")
    if status in INQUIRY_STATUSES:
        return redirect(url_for("admin.crm", status=status))
    return redirect(url_for("admin.crm"))


@bp.route("/inquiries/<int:inquiry_id>", methods=["GET", "POST"])
@permission_required("crm.view")
def inquiry(inquiry_id):
    row = db.session.get(ContactSubmission, inquiry_id)
    if row is None:
        abort(404)
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("crm.edit",)):
            abort(403)
        error = _apply_inquiry(row)
        if not error:
            record_audit("update", "lead", row.id, row.status)
            db.session.commit()
            flash("Inquiry updated.")
            return redirect(url_for("admin.inquiry", inquiry_id=row.id))
    return _render("admin/inquiry.html", title=row.name or "Lead", row=row, statuses=INQUIRY_STATUSES, staff=_lead_staff(), error=error, today=date.today())


@bp.route("/inquiries/<int:inquiry_id>/delete", methods=["POST"])
@permission_required("crm.edit")
def inquiry_delete(inquiry_id):
    row = db.session.get(ContactSubmission, inquiry_id)
    if row is None:
        abort(404)
    record_audit("delete", "lead", row.id, row.email)
    db.session.delete(row)
    db.session.commit()
    flash("Lead removed.")
    return redirect(url_for("admin.crm"))


@bp.route("/applications", methods=["GET", "POST"])
@permission_required("careers.view")
def applications():
    if request.method == "POST":
        if not g.staff.has_any(("careers.edit", "crm.edit")):
            abort(403)
        row = db.session.get(JobApplication, request.form.get("application_id", type=int))
        status = request.form.get("status", "")
        if row and status in APPLICATION_STATUSES:
            row.status = status
            db.session.commit()
            flash("Application updated.")
        return redirect(url_for("admin.applications"))
    rows = JobApplication.query.order_by(JobApplication.created_at.desc()).all()
    return _render("admin/applications.html", title="Applications", rows=rows, statuses=APPLICATION_STATUSES)


@bp.route("/applications/<int:application_id>/cv")
@permission_required("careers.view", "crm.view")
def application_cv(application_id):
    row = db.session.get(JobApplication, application_id)
    stored = os.path.basename(row.cv_filename or "") if row else ""
    directory = os.path.realpath(current_app.config["UPLOAD_FOLDER"])
    path = os.path.realpath(os.path.join(directory, stored)) if stored else ""
    if row is None or not stored or not path.startswith(directory + os.sep) or not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=row.cv_original_name or stored, max_age=0)


@bp.route("/insights")
@permission_required("content.view")
def articles():
    rows = Article.query.order_by(Article.updated_at.desc()).all()
    return _render("admin/articles.html", title="Insights", rows=rows)


@bp.route("/insights/new", methods=["GET", "POST"])
@permission_required("content.edit")
def article_new():
    return _article_form(Article(status="draft", author="Neural Xpert"))


@bp.route("/insights/<int:article_id>", methods=["GET", "POST"])
@permission_required("content.view")
def article_edit(article_id):
    article = db.session.get(Article, article_id)
    if article is None:
        abort(404)
    return _article_form(article)


def _article_form(article):
    categories = Category.query.filter_by(kind="article").order_by(Category.name).all()
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("content.edit",)):
            abort(403)
        if request.form.get("delete") == "1" and article.id:
            db.session.delete(article)
            record_audit("delete", "article", article.id, article.title)
            db.session.commit()
            flash("Insight removed.")
            return redirect(url_for("admin.articles"))
        title = (request.form.get("title") or "").strip()
        excerpt = (request.form.get("excerpt") or "").strip()
        if not title or not excerpt:
            error = "Title and excerpt are required."
        else:
            article.title = title[:255]
            article.slug = _unique_slug(Article, request.form.get("slug") or title, article.id)
            article.author = (request.form.get("author") or article.author or "Neural Xpert")[:120]
            article.featured = request.form.get("featured") == "1"
            article.excerpt = excerpt
            article.content = sanitize_html(request.form.get("content") or "")
            image_error = apply_managed_image(article, "featured_image", "featured_image_file", "image_width", "image_height", "image_radius")
            if image_error:
                error = image_error
            else:
                article.seo_title = (request.form.get("seo_title") or title)[:255]
                article.meta_description = (request.form.get("meta_description") or excerpt)[:320]
                requested = request.form.get("status") if request.form.get("status") in ARTICLE_STATUSES else "draft"
                if requested == "published" and not g.staff.has_any(("content.publish",)):
                    requested = "review"
                article.status = requested
                article.tags = (request.form.get("tags") or "")[:500]
                article.focus_keyword = (request.form.get("focus_keyword") or "")[:160]
                article.canonical_url = safe_url(request.form.get("canonical_url") or "")
                article.robots = (request.form.get("robots") or "")[:80]
                article.cta_label = (request.form.get("cta_label") or "")[:120]
                article.cta_url = safe_url(request.form.get("cta_url") or "")
                og_upload = request.files.get("og_image_file")
                if og_upload is not None and og_upload.filename:
                    stored, notice = save_public_image(og_upload)
                    if notice:
                        error = notice
                    else:
                        article.og_image = stored
                else:
                    article.og_image = safe_static_path(request.form.get("og_image") or "") or safe_url(request.form.get("og_image") or "")
                if not error:
                    if "blocks" in request.form:
                        article.blocks = (request.form.get("blocks") or "")[:20000]
                    new_category = (request.form.get("new_category") or "").strip()
                    if new_category:
                        category_slug = slugify(new_category) or "category"
                        existing = Category.query.filter_by(slug=category_slug, kind="article").first()
                        if existing is None:
                            existing = Category(name=new_category[:120], slug=_unique_slug(Category, new_category), kind="article")
                            db.session.add(existing)
                            db.session.flush()
                        article.category = existing
                    else:
                        category_id = request.form.get("category_id", type=int)
                        article.category = db.session.get(Category, category_id) if category_id else None
                    article.managed_in_admin = True
                    if article.status == "published" and article.published_at is None:
                        article.published_at = utcnow()
                    if article.id is None:
                        db.session.add(article)
                    db.session.commit()
                    flash("Insight saved.")
                    return redirect(url_for("admin.article_edit", article_id=article.id))
    return _render("admin/article_form.html", title=article.title or "New insight", article=article, categories=categories, error=error, statuses=ARTICLE_STATUSES)


@bp.route("/case-studies", methods=["GET", "POST"])
@permission_required("content.view")
def studies():
    from app.admin.catalog import ensure_catalog
    from app.models.platform import SitePage

    ensure_catalog()
    if request.method == "POST":
        if not g.staff.has_any(("content.edit",)):
            abort(403)
        page = SitePage.query.filter_by(key="case-studies").first()
        if page is None:
            abort(404)
        image_error = apply_page_style(page)
        if image_error:
            flash(image_error)
        else:
            record_audit("save", "page", page.id, "case studies appearance")
            db.session.commit()
            flash("Case studies page updated.")
        return redirect(url_for("admin.studies"))
    status = request.args.get("status", "")
    term = (request.args.get("q") or "").strip()
    query = CaseStudy.query
    if status in ARTICLE_STATUSES:
        query = query.filter_by(status=status)
    if term:
        like = f"%{term}%"
        query = query.filter(
            CaseStudy.title.ilike(like)
            | CaseStudy.industry.ilike(like)
            | CaseStudy.client_display_name.ilike(like)
            | CaseStudy.category.ilike(like)
        )
    rows = query.order_by(CaseStudy.updated_at.desc(), CaseStudy.id.desc()).all()
    counts = {item: CaseStudy.query.filter_by(status=item).count() for item in ARTICLE_STATUSES}
    return _render(
        "admin/studies.html",
        title="Case studies",
        rows=rows,
        status=status if status in ARTICLE_STATUSES else "",
        q=term,
        counts=counts,
        total=CaseStudy.query.count(),
        statuses=ARTICLE_STATUSES,
        listing=SitePage.query.filter_by(key="case-studies").first(),
        fonts=FONT_CHOICES,
    )


@bp.route("/case-studies/new", methods=["GET", "POST"])
@permission_required("content.edit")
def study_new():
    return _study_form(CaseStudy(title="", slug="draft", status="draft"))


@bp.route("/case-studies/<int:study_id>", methods=["GET", "POST"])
@permission_required("content.view")
def study_edit(study_id):
    study = db.session.get(CaseStudy, study_id)
    if study is None:
        abort(404)
    return _study_form(study)


def _study_form(study):
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("content.edit",)):
            abort(403)
        if request.form.get("delete") == "1" and study.id:
            db.session.delete(study)
            record_audit("delete", "case_study", study.id, study.title)
            db.session.commit()
            flash("Case study removed.")
            return redirect(url_for("admin.studies"))
        title = (request.form.get("title") or "").strip()
        summary = (request.form.get("summary") or "").strip()
        if not title or not summary:
            error = "Title and summary are required."
        else:
            study.title = title[:255]
            study.slug = _unique_slug(CaseStudy, title, study.id)
            study.summary = summary
            study.content = sanitize_html(request.form.get("content") or "")
            study.challenge = (request.form.get("challenge") or "")[:5000]
            study.solution = (request.form.get("solution") or "")[:5000]
            study.architecture = (request.form.get("architecture") or "")[:5000]
            study.results = (request.form.get("results") or "")[:5000]
            study.industry = (request.form.get("industry") or "")[:120]
            study.category = (request.form.get("category") or "")[:120]
            study.technologies = (request.form.get("technologies") or "")[:500]
            study.client_name = (request.form.get("client_name") or "")[:255]
            study.client_display_name = (request.form.get("client_display_name") or "")[:255]
            image_error = apply_managed_image(study, "featured_image", "featured_image_file", "image_width", "image_height", "image_radius")
            if not image_error:
                image_error = apply_managed_image(study, "architecture_image", "architecture_image_file", "arch_width", "arch_height", "arch_radius")
            if image_error:
                error = image_error
            else:
                study.seo_title = (request.form.get("seo_title") or "")[:255]
                study.meta_description = (request.form.get("meta_description") or "")[:320]
                requested = request.form.get("status") if request.form.get("status") in ARTICLE_STATUSES else "draft"
                if requested == "published" and not g.staff.has_any(("content.publish",)):
                    requested = "review"
                study.status = requested
                study.customer_quote = (request.form.get("customer_quote") or "")[:5000]
                study.metrics = (request.form.get("metrics") or "")[:5000] if request.form.get("metrics_verified") == "1" else ""
                study.metrics_verified = request.form.get("metrics_verified") == "1"
                study.cloud_platform = (request.form.get("cloud_platform") or "")[:255]
                study.data_sources = (request.form.get("data_sources") or "")[:5000]
                study.integrations = (request.form.get("integrations") or "")[:5000]
                study.security_controls = (request.form.get("security_controls") or "")[:5000]
                study.implementation = (request.form.get("implementation") or "")[:5000]
                apply_card_type(study)
                study.managed_in_admin = True
                if study.status == "published" and study.published_at is None:
                    study.published_at = utcnow()
                if study.id is None:
                    db.session.add(study)
                db.session.commit()
                flash("Case study saved.")
                return redirect(url_for("admin.study_edit", study_id=study.id))
    return _render("admin/study_form.html", title=study.title or "New case study", study=study, error=error, statuses=ARTICLE_STATUSES, fonts=FONT_CHOICES)


@bp.route("/careers")
@permission_required("careers.view")
def careers():
    rows = Job.query.order_by(Job.updated_at.desc()).all()
    return _render("admin/careers.html", title="Careers", rows=rows)


@bp.route("/careers/new", methods=["GET", "POST"])
@permission_required("careers.edit")
def career_new():
    return _career_form(Job(status="draft"))


@bp.route("/careers/<int:job_id>", methods=["GET", "POST"])
@permission_required("careers.view")
def career_edit(job_id):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    return _career_form(job)


def _career_form(job):
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("careers.edit",)):
            abort(403)
        if request.form.get("delete") == "1" and job.id:
            if job.applications:
                error = "This opening has applications, so it cannot be removed. Set the status to closed."
            else:
                db.session.delete(job)
                record_audit("delete", "job", job.id, job.title)
                db.session.commit()
                flash("Opening removed.")
                return redirect(url_for("admin.careers"))
        title = (request.form.get("title") or "").strip() if not error else ""
        if error:
            pass
        elif not title:
            error = "Title is required."
        else:
            job.title = title[:255]
            job.slug = _unique_slug(Job, request.form.get("slug") or title, job.id)
            job.department = (request.form.get("department") or "")[:120]
            job.location = (request.form.get("location") or "")[:120]
            job.employment_type = (request.form.get("employment_type") or "")[:80]
            job.description = sanitize_html(request.form.get("description") or "")
            job.requirements = sanitize_html(request.form.get("requirements") or "")
            job.responsibilities = sanitize_html(request.form.get("responsibilities") or "")
            job.experience = (request.form.get("experience") or "")[:5000]
            job.workplace = (request.form.get("workplace") or "")[:40]
            raw_close = (request.form.get("closing_on") or "").strip()
            try:
                job.closing_on = date.fromisoformat(raw_close) if raw_close else None
            except ValueError:
                error = "Use a YYYY-MM-DD closing date."
            job.status = request.form.get("status") if request.form.get("status") in JOB_STATUSES else "draft"
            if job.status in ("published", "open") and job.published_at is None:
                job.published_at = utcnow()
            if not error:
                if job.id is None:
                    db.session.add(job)
                db.session.commit()
                flash("Opening saved.")
                return redirect(url_for("admin.career_edit", job_id=job.id))
    return _render("admin/career_form.html", title=job.title or "New opening", job=job, error=error, statuses=JOB_STATUSES)


def _active_admin_count(except_id=None):
    role = StaffRole.query.filter_by(slug="administrator").first()
    if role is None:
        return 0
    query = StaffUser.query.filter_by(role_id=role.id, is_active=True)
    if except_id:
        query = query.filter(StaffUser.id != except_id)
    return query.count()


@bp.route("/users", methods=["GET", "POST"])
@permission_required("users.manage")
def users():
    ensure_roles()
    error = ""
    provisioned = None
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        name = (request.form.get("name") or "").strip()[:120]
        role = db.session.get(StaffRole, request.form.get("role_id", type=int))
        if not email:
            error = "Enter a valid email address."
        elif StaffUser.query.filter_by(email=email).first():
            error = "That staff account already exists."
        elif role is None:
            error = "Choose a role."
        else:
            from app.admin.security import create_staff

            staff, password = create_staff(email, role=role, name=name)
            session["provisioned_staff"] = {"email": staff.email, "password": password}
            flash("Staff account created.")
            return redirect(url_for("admin.users"))
    else:
        provisioned = session.pop("provisioned_staff", None)
    rows = StaffUser.query.order_by(StaffUser.email).all()
    roles = StaffRole.query.order_by(StaffRole.name).all()
    return _render(
        "admin/users.html",
        title="Users",
        rows=rows,
        roles=roles,
        error=error,
        provisioned=provisioned,
    )


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@permission_required("users.manage")
def user_edit(user_id):
    ensure_roles()
    person = db.session.get(StaffUser, user_id)
    if person is None:
        abort(404)
    error = ""
    reset = None
    if request.method == "POST" and request.form.get("action") == "reset":
        if person.id == g.staff.id:
            error = "Change your own password from Account."
        else:
            import secrets

            password = secrets.token_urlsafe(18)
            person.password_hash = generate_password_hash(password)
            person.failed_attempts = 0
            person.locked_until = None
            record_audit("reset_password", "staff", person.id, person.email)
            db.session.commit()
            session["reset_password"] = {"user_id": person.id, "email": person.email, "password": password}
            flash("A temporary password was created. It is shown once.")
            return redirect(url_for("admin.user_edit", user_id=person.id))
    elif request.method == "POST" and request.form.get("action") == "reset_mfa":
        if person.id == g.staff.id:
            error = "You cannot clear your own authenticator from this page."
        else:
            person.totp_secret = ""
            person.totp_enabled = False
            person.last_totp_step = 0
            person.recovery_hashes = ""
            record_audit("reset_mfa", "staff", person.id, person.email)
            db.session.commit()
            flash("Authenticator cleared. They set it up again at the next sign-in.")
            return redirect(url_for("admin.user_edit", user_id=person.id))
    elif request.method == "POST":
        role = db.session.get(StaffRole, request.form.get("role_id", type=int))
        active = request.form.get("is_active") == "1"
        if role is None:
            error = "Choose a role."
        elif person.id == g.staff.id and not active:
            error = "You cannot deactivate your own account."
        elif person.role and person.role.slug == "administrator" and person.is_active and (not active or role.slug != "administrator") and _active_admin_count(person.id) == 0:
            error = "Keep at least one active administrator."
        else:
            person.name = (request.form.get("name") or "").strip()[:120]
            person.role = role
            person.is_active = active
            db.session.commit()
            flash("User updated.")
            return redirect(url_for("admin.user_edit", user_id=person.id))
    else:
        pending = session.get("reset_password") or {}
        if pending.get("user_id") == person.id:
            reset = session.pop("reset_password")
    roles = StaffRole.query.order_by(StaffRole.name).all()
    return _render("admin/user_form.html", title=person.email, person=person, roles=roles, error=error, reset=reset)


@bp.route("/access-roles", methods=["GET", "POST"])
@permission_required("roles.manage")
def access_roles():
    ensure_roles()
    error = ""
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            error = "Enter a role name."
        else:
            role = StaffRole(name=name[:80], slug=_unique_slug(StaffRole, name), permissions="overview", is_system=False)
            db.session.add(role)
            db.session.commit()
            flash("Role created.")
            return redirect(url_for("admin.access_role_edit", role_id=role.id))
    rows = StaffRole.query.order_by(StaffRole.name).all()
    return _render("admin/access_roles.html", title="Roles and permissions", rows=rows, error=error)


@bp.route("/access-roles/<int:role_id>", methods=["GET", "POST"])
@permission_required("roles.manage")
def access_role_edit(role_id):
    ensure_roles()
    role = db.session.get(StaffRole, role_id)
    if role is None:
        abort(404)
    error = ""
    if request.method == "POST":
        if request.form.get("delete") == "1":
            if role.is_system or role.users:
                error = "This role cannot be deleted."
            else:
                db.session.delete(role)
                db.session.commit()
                flash("Role deleted.")
                return redirect(url_for("admin.access_roles"))
        elif role.is_system:
            error = "The administrator role keeps every permission."
        else:
            selected = [code for code, _label, _group in PERMISSIONS if request.form.get(f"perm_{code}")]
            if "overview" not in selected:
                selected.insert(0, "overview")
            role.name = (request.form.get("name") or role.name).strip()[:80]
            role.permissions = ",".join(selected)
            db.session.commit()
            flash("Permissions updated.")
            return redirect(url_for("admin.access_role_edit", role_id=role.id))
    return _render("admin/access_role_form.html", title=role.name, role=role, permissions=PERMISSIONS, error=error)


from app.admin.platform import register as register_platform

register_platform(bp)
