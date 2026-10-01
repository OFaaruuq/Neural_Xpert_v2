import csv
import io
import json
import os
import re
import uuid
from datetime import date, timedelta

from flask import abort, flash, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from app.services import file_signature_ok, safe_local_path, safe_static_path, safe_url
from app.admin.catalog import (
    ensure_catalog,
    record_audit,
    record_revision,
    seo_checks,
    setting_value,
)
from app.extensions import db
from app.models import Article, CaseStudy, Job
from app.models.platform import (
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
from app.services import sanitize_html, slugify
from app.visitors import traffic_summary

PUBLISH_STATUSES = ("draft", "review", "scheduled", "published", "archived")
OFFER_FIELDS = (
    ("name", "Name", "text"),
    ("slug", "Slug", "text"),
    ("summary", "Short description", "area"),
    ("body", "Full content", "area"),
    ("hero_image", "Hero image", "text"),
    ("icon", "Icon", "text"),
    ("challenges", "Challenges", "area"),
    ("capabilities", "Capabilities", "area"),
    ("architecture", "Architecture", "area"),
    ("benefits", "Benefits", "area"),
    ("use_cases", "Use cases", "area"),
    ("cta_label", "CTA label", "text"),
    ("cta_url", "CTA link", "text"),
    ("seo_title", "SEO title", "text"),
    ("meta_description", "Meta description", "area"),
    ("focus_keyword", "Focus keyword", "text"),
)


def _render(template, **context):
    context.setdefault("title", "Admin")
    return render_template(template, **context)


def _unique_kind_slug(kind, source, current_id=None):
    base = (slugify(source) or "item")[:140]
    slug = base
    number = 2
    while True:
        existing = Offering.query.filter_by(kind=kind, slug=slug).first()
        if existing is None or existing.id == current_id:
            return slug
        slug = f"{base}-{number}"[:160]
        number += 1


def _unique_section_key(source):
    base = (slugify(source) or "section")[:70]
    key = base
    number = 2
    while HomeSection.query.filter_by(key=key).first():
        key = f"{base}-{number}"[:80]
        number += 1
    return key


def _publish_status(current):
    status = request.form.get("status") if request.form.get("status") in PUBLISH_STATUSES else current or "draft"
    if status == "published" and not g.staff.has_any(("content.publish",)):
        return "review"
    return status


def _offering_list(kind, title, endpoint):
    ensure_catalog()
    rows = Offering.query.filter_by(kind=kind).order_by(Offering.position, Offering.name).all()
    return _render("admin/module_list.html", title=title, rows=rows, kind=kind, endpoint=endpoint, create_url=url_for(endpoint + "_new"))


def _offering_form(kind, item, endpoint):
    ensure_catalog()
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("content.edit",)):
            abort(403)
        name = (request.form.get("name") or "").strip()
        if not name:
            error = "Name is required."
        else:
            item.kind = kind
            item.name = name[:255]
            item.slug = _unique_kind_slug(kind, request.form.get("slug") or name, item.id)
            for field, _label, kind_name in OFFER_FIELDS:
                if field in {"name", "slug"}:
                    continue
                value = request.form.get(field) or ""
                if kind_name == "area":
                    value = sanitize_html(value) if field == "body" else value
                setattr(item, field, value[:5000] if kind_name == "area" else value[:500])
            item.featured = request.form.get("featured") == "1"
            item.status = _publish_status(item.status)
            if item.id is None:
                db.session.add(item)
                db.session.flush()
            record_revision(item, f"Saved {kind}")
            record_audit("save", kind, item.id, item.name)
            db.session.commit()
            flash(f"{kind.title()} saved.")
            return redirect(url_for(endpoint + "_edit", item_id=item.id))
    grade, checks = seo_checks(item.seo_title or item.name, item.meta_description or item.summary, item.name, bool(item.hero_image or item.icon), True, True)
    return _render(
        "admin/module_form.html",
        title=item.name or f"New {kind}",
        item=item,
        fields=OFFER_FIELDS,
        error=error,
        statuses=PUBLISH_STATUSES,
        grade=grade,
        checks=checks,
        back=url_for(endpoint),
        preview=url_for("admin.preview_offering", item_id=item.id) if item.id else "",
    )


def pages():
    ensure_catalog()
    rows = SitePage.query.order_by(SitePage.title).all()
    return _render("admin/pages.html", title="Pages", rows=rows)


def page_edit(page_id):
    ensure_catalog()
    page = db.session.get(SitePage, page_id)
    if page is None:
        abort(404)
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("content.edit",)):
            abort(403)
        page.title = (request.form.get("title") or page.title).strip()[:255]
        page.hero_title = (request.form.get("hero_title") or "")[:255]
        page.hero_subtitle = (request.form.get("hero_subtitle") or "")[:2000]
        page.hero_image = safe_static_path(request.form.get("hero_image") or "")
        page.summary = (request.form.get("summary") or "")[:5000]
        page.cta_label = (request.form.get("cta_label") or "")[:120]
        page.cta_url = safe_url(request.form.get("cta_url") or "")
        page.seo_title = (request.form.get("seo_title") or "")[:255]
        page.meta_description = (request.form.get("meta_description") or "")[:320]
        page.focus_keyword = (request.form.get("focus_keyword") or "")[:160]
        page.canonical_url = safe_url(request.form.get("canonical_url") or "")
        page.og_title = (request.form.get("og_title") or "")[:255]
        page.og_description = (request.form.get("og_description") or "")[:320]
        page.og_image = safe_static_path(request.form.get("og_image") or "") or safe_url(request.form.get("og_image") or "")
        page.robots = (request.form.get("robots") or "")[:80]
        page.status = _publish_status(page.status)
        record_revision(page, "Page saved")
        record_audit("save", "page", page.id, page.title)
        db.session.commit()
        flash("Page saved.")
        return redirect(url_for("admin.page_edit", page_id=page.id))
    grade, checks = seo_checks(page.seo_title or page.hero_title or page.title, page.meta_description or page.summary, page.hero_title or page.title)
    return _render("admin/page_form.html", title=page.title, page=page, error=error, statuses=PUBLISH_STATUSES, grade=grade, checks=checks)


def homepage():
    ensure_catalog()
    if request.method == "POST":
        if not g.staff.has_any(("content.edit",)):
            abort(403)
        action = request.form.get("action")
        section = db.session.get(HomeSection, request.form.get("section_id", type=int))
        if section is None:
            abort(404)
        if action == "toggle":
            section.enabled = not section.enabled
        elif action == "save":
            section.eyebrow = (request.form.get("eyebrow") or "")[:160]
            section.headline = (request.form.get("headline") or "")[:255]
            section.summary = (request.form.get("summary") or "")[:2000]
            section.cta_label = (request.form.get("cta_label") or "")[:120]
            section.cta_url = safe_url(request.form.get("cta_url") or "")
        elif action in {"up", "down"}:
            direction = -1 if action == "up" else 1
            ordered = HomeSection.query.order_by(HomeSection.position, HomeSection.id).all()
            index = next((i for i, row in enumerate(ordered) if row.id == section.id), None)
            swap = index + direction if index is not None else None
            if swap is not None and 0 <= swap < len(ordered):
                ordered[index].position, ordered[swap].position = ordered[swap].position, ordered[index].position
        elif action == "duplicate":
            copy = HomeSection(
                key=_unique_section_key(section.key + "-copy"),
                name=section.name + " copy",
                position=section.position + 1,
                enabled=False,
                eyebrow=section.eyebrow,
                headline=section.headline,
                summary=section.summary,
                cta_label=section.cta_label,
                cta_url=section.cta_url,
            )
            db.session.add(copy)
        record_audit("homepage", "home_section", section.id, action or "")
        db.session.commit()
        flash("Homepage updated.")
        return redirect(url_for("admin.homepage"))
    rows = HomeSection.query.order_by(HomeSection.position, HomeSection.id).all()
    return _render("admin/homepage.html", title="Homepage", rows=rows)


def media():
    ensure_catalog()
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("media.manage", "content.edit")):
            abort(403)
        upload = request.files.get("file")
        alt = (request.form.get("alt_text") or "").strip()
        if upload is None or not upload.filename:
            error = "Choose a file."
        elif not alt:
            error = "ALT text is required."
        else:
            ext = os.path.splitext(upload.filename)[1].lower()
            header = upload.stream.read(16)
            upload.stream.seek(0)
            if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"} or not file_signature_ok(ext, header):
                error = "Use a PNG, JPG, WEBP, GIF, or PDF file."
            else:
                from flask import current_app

                folder = secure_filename(request.form.get("folder") or "general") or "general"
                stored = f"{uuid.uuid4().hex}{ext}"
                directory = os.path.join(current_app.config["UPLOAD_FOLDER"], "media")
                os.makedirs(directory, exist_ok=True)
                path = os.path.join(directory, stored)
                upload.save(path)
                asset = MediaAsset(
                    filename=stored,
                    original_name=secure_filename(upload.filename)[:255],
                    alt_text=alt[:255],
                    title=(request.form.get("title") or alt)[:255],
                    folder=folder[:80],
                    size=os.path.getsize(path),
                    uploaded_by_id=g.staff.id,
                )
                db.session.add(asset)
                record_audit("upload", "media", stored, alt)
                db.session.commit()
                flash("File added to the library.")
                return redirect(url_for("admin.media"))
    folder = request.args.get("folder", "")
    query = MediaAsset.query
    if folder:
        query = query.filter_by(folder=folder)
    rows = query.order_by(MediaAsset.created_at.desc()).all()
    return _render("admin/media.html", title="Media library", rows=rows, error=error, folder=folder)


def media_file(asset_id, filename):
    from flask import current_app

    from app.admin.security import current_staff, session_is_fresh

    if not session.get("mfa_complete"):
        return redirect(url_for("admin.login"))
    staff = current_staff()
    if staff is None or not session_is_fresh():
        return redirect(url_for("admin.login"))
    if not staff.has_any(("content.view", "media.manage", "content.edit")):
        abort(403)
    asset = db.session.get(MediaAsset, asset_id)
    stored = os.path.basename(filename or "")
    if asset is None or asset.filename != stored or stored != os.path.basename(asset.filename):
        abort(404)
    directory = os.path.realpath(os.path.join(current_app.config["UPLOAD_FOLDER"], "media"))
    path = os.path.realpath(os.path.join(directory, stored))
    if not path.startswith(directory + os.sep) or not os.path.isfile(path):
        abort(404)
    attachment = stored.lower().endswith(".pdf")
    return send_file(
        path,
        as_attachment=attachment,
        download_name=asset.original_name or stored,
        max_age=0,
    )


def navigation():
    ensure_catalog()
    if request.method == "POST":
        if not g.staff.has_any(("settings.manage", "content.edit")):
            abort(403)
        if request.form.get("create") == "1":
            label = (request.form.get("label") or "").strip()
            if label:
                db.session.add(
                    NavItem(
                        menu=request.form.get("menu") if request.form.get("menu") in {"header", "footer"} else "header",
                        label=label[:120],
                        url=safe_url(request.form.get("url") or "/") or "/",
                        enabled=False,
                        position=NavItem.query.count() + 1,
                    )
                )
        else:
            item = db.session.get(NavItem, request.form.get("item_id", type=int))
            if item:
                item.label = (request.form.get("label") or item.label)[:120]
                item.url = safe_url(request.form.get("url") or item.url) or item.url
                item.enabled = request.form.get("enabled") == "1"
                item.new_tab = request.form.get("new_tab") == "1"
                item.menu = request.form.get("menu") if request.form.get("menu") in {"header", "footer"} else item.menu
        record_audit("navigation", "nav", "", "updated")
        db.session.commit()
        flash("Navigation saved. The public menu changes only for items you enable.")
        return redirect(url_for("admin.navigation"))
    rows = NavItem.query.order_by(NavItem.menu, NavItem.position, NavItem.id).all()
    return _render("admin/navigation.html", title="Navigation", rows=rows)


def seo():
    ensure_catalog()
    rows = []
    for page in SitePage.query.order_by(SitePage.title).all():
        grade, checks = seo_checks(page.seo_title or page.hero_title, page.meta_description or page.summary, page.hero_title or page.title)
        rows.append((page.title, grade, checks, url_for("admin.page_edit", page_id=page.id)))
    for article in Article.query.order_by(Article.updated_at.desc()).limit(30):
        grade, checks = seo_checks(article.seo_title, article.meta_description, article.title, bool(article.featured_image))
        rows.append((article.title, grade, checks, url_for("admin.article_edit", article_id=article.id)))
    return _render("admin/seo.html", title="SEO", rows=rows)


def analytics():
    traffic = traffic_summary()
    leads = ConversionEvent.query.filter_by(name="contact_submit").count()
    from app.models import DailyPageView

    total_views = db.session.query(db.func.coalesce(db.func.sum(DailyPageView.views), 0)).scalar() or 0
    return _render("admin/analytics.html", title="Analytics", traffic=traffic, leads=leads, total_views=total_views)


def conversions():
    names = ("contact_submit", "article_view", "case_study_view", "offering_view", "cta_click")
    counts = {name: ConversionEvent.query.filter_by(name=name).count() for name in names}
    recent = ConversionEvent.query.order_by(ConversionEvent.created_at.desc()).limit(20).all()
    return _render("admin/conversions.html", title="Conversions", counts=counts, recent=recent)


def settings():
    from app.brand import logo_slots, remove_stored, store_logo

    ensure_catalog()
    if request.method == "POST":
        if not g.staff.has_any(("settings.manage",)):
            abort(403)
        for row in SiteSetting.query.all():
            if row.key.startswith("logo_") or row.key.startswith("ask_ai_"):
                continue
            if row.key in request.form:
                raw = (request.form.get(row.key) or "")[:2000]
                if row.key == "analytics_id":
                    raw = raw if re.fullmatch(r"[A-Za-z0-9_-]{0,40}", raw.strip()) else ""
                elif row.key.endswith("_url") or row.key.startswith("social_"):
                    raw = safe_url(raw)
                row.value = raw
        notice = ""
        pending = []
        for row in SiteSetting.query.filter(SiteSetting.key.startswith("logo_")).all():
            upload = request.files.get(row.key)
            if upload is not None and upload.filename:
                stored, notice = store_logo(upload)
                if notice:
                    break
                pending.append((row, stored))
            elif request.form.get(f"clear_{row.key}") == "1":
                pending.append((row, ""))
        if notice:
            for _row, stored in pending:
                remove_stored(stored)
            db.session.rollback()
            flash(notice)
            return redirect(url_for("admin.settings"))
        for row, stored in pending:
            if row.value != stored:
                remove_stored(row.value)
            row.value = stored
        record_audit("settings", "settings", "", "updated")
        db.session.commit()
        flash("Settings saved.")
        return redirect(url_for("admin.settings"))
    rows = SiteSetting.query.order_by(SiteSetting.key).all()
    return _render(
        "admin/settings.html",
        title="Settings",
        rows=rows,
        logos=logo_slots(),
        contact_email=setting_value("contact_email"),
    )


def ask_ai_settings():
    from app.ai_support import admin_state, audit_detail, save_settings, test_connection

    if request.method == "POST":
        if not g.staff.has_any(("settings.manage",)):
            abort(403)
        error = save_settings(request.form)
        if error:
            db.session.rollback()
            flash(error)
            return redirect(url_for("admin.ask_ai_settings"))
        record_audit("ask_ai", "settings", "", audit_detail(request.form))
        db.session.commit()
        if request.form.get("action") == "test":
            _ok, notice = test_connection()
            flash(notice)
        else:
            flash("ASK AI settings saved.")
        return redirect(url_for("admin.ask_ai_settings"))
    return _render("admin/ask_ai.html", title="ASK AI", ask=admin_state())


def email_settings():
    from app.mailer import mail_form_state, save_mail_settings, send_test_to

    ensure_catalog()
    if request.method == "POST":
        if not g.staff.has_any(("settings.manage",)):
            abort(403)
        error = save_mail_settings(request.form)
        if error:
            db.session.rollback()
            flash(error)
            return redirect(url_for("admin.email_settings"))
        record_audit("email", "settings", "", "smtp updated")
        if request.form.get("action") == "test":
            db.session.commit()
            _ok, notice = send_test_to(g.staff.email)
            flash(notice)
        else:
            db.session.commit()
            flash("Email settings saved.")
        return redirect(url_for("admin.email_settings"))
    return _render("admin/email.html", title="Email", mail=mail_form_state())


def audit_logs():
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return _render("admin/audit.html", title="Audit logs", rows=rows)


def health():
    ensure_catalog()
    missing_seo = Article.query.filter(Article.status == "published", Article.meta_description == "").count()
    missing_alt = MediaAsset.query.filter(MediaAsset.alt_text == "").count()
    drafts = Offering.query.filter(Offering.status.in_(("draft", "review"))).count()
    rules = RedirectRule.query.filter_by(enabled=True).count()
    soon = date.today() + timedelta(days=60)
    expiring = Credential.query.filter(Credential.expires_on.isnot(None), Credential.expires_on <= soon).count()
    return _render(
        "admin/health.html",
        title="Site health",
        missing_seo=missing_seo,
        missing_alt=missing_alt,
        drafts=drafts,
        rules=rules,
        expiring=expiring,
    )


def redirects():
    error = ""
    if request.method == "POST":
        if not g.staff.has_any(("settings.manage", "content.edit")):
            abort(403)
        source = safe_local_path(request.form.get("source") or "")
        target = safe_local_path(request.form.get("target") or "")
        if not source or not target or source == target:
            error = "Use an internal path such as /old-page and a destination."
        elif RedirectRule.query.filter_by(source=source).first():
            error = "That path already redirects."
        else:
            db.session.add(RedirectRule(source=source[:300], target=target[:500], enabled=True))
            record_audit("redirect", "redirect", source, target)
            db.session.commit()
            flash("Redirect saved.")
            return redirect(url_for("admin.redirects"))
    rows = RedirectRule.query.order_by(RedirectRule.source).all()
    return _render("admin/redirects.html", title="Redirects", rows=rows, error=error)


def backups():
    return _render("admin/backups.html", title="Backups")


def revisions():
    rows = ContentRevision.query.order_by(ContentRevision.created_at.desc()).limit(100).all()
    return _render("admin/revisions.html", title="Revision history", rows=rows)


def workflow():
    ensure_catalog()
    waiting = []
    waiting.extend(("Insight", row.title, row.status, url_for("admin.article_edit", article_id=row.id)) for row in Article.query.filter(Article.status.in_(("draft", "review", "scheduled"))).all())
    waiting.extend(("Case study", row.title, row.status, url_for("admin.study_edit", study_id=row.id)) for row in CaseStudy.query.filter(CaseStudy.status.in_(("draft", "review", "scheduled"))).all())
    for row in Offering.query.filter(Offering.status.in_(("draft", "review", "scheduled"))).all():
        endpoint = {"solution": "admin.solutions_edit", "service": "admin.services_edit", "industry": "admin.industries_edit"}[row.kind]
        waiting.append((row.kind.title(), row.name, row.status, url_for(endpoint, item_id=row.id)))
    return _render("admin/workflow.html", title="Publishing workflow", rows=waiting)


def search():
    term = (request.args.get("q") or "").strip()
    like = f"%{term.replace('%', '').replace('_', '')}%"
    pages = SitePage.query.filter(SitePage.title.ilike(like)).limit(10).all() if term else []
    articles = Article.query.filter(Article.title.ilike(like)).limit(10).all() if term else []
    offerings = Offering.query.filter(Offering.name.ilike(like)).limit(10).all() if term else []
    from app.models import ContactSubmission

    leads = ContactSubmission.query.filter(ContactSubmission.name.ilike(like) | ContactSubmission.email.ilike(like)).limit(10).all() if term else []
    return _render("admin/search.html", title="Search", term=term, pages=pages, articles=articles, offerings=offerings, leads=leads)


def leads_export():
    if not g.staff.has_any(("leads.export", "crm.edit")):
        abort(403)
    from app.models import ContactSubmission

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Company", "Email", "Phone", "Job title", "Country", "Subject", "Interest", "Message", "Status", "Owner", "Follow-up", "Source", "UTM", "Notes", "Created"])
    for row in ContactSubmission.query.filter_by(archived=False).order_by(ContactSubmission.created_at.desc()).all():
        owner = row.assigned_to.display_name if row.assigned_to else ""
        writer.writerow([
            row.name, row.company, row.email, row.phone, row.job_title, row.country,
            row.subject, row.interest, row.message, row.status, owner,
            row.follow_up_on.isoformat() if row.follow_up_on else "",
            row.source_page, row.utm_source, row.notes,
            row.created_at.isoformat() if row.created_at else "",
        ])
    record_audit("export", "leads", "", "csv")
    db.session.commit()
    payload = io.BytesIO(buffer.getvalue().encode("utf-8"))
    return send_file(payload, mimetype="text/csv", as_attachment=True, download_name="neural-xpert-leads.csv")


def preview_offering(item_id):
    item = db.session.get(Offering, item_id)
    if item is None:
        abort(404)
    return render_template("main/offering.html", item=item, preview=True, seo_title=item.seo_title or item.name, meta_description=item.meta_description or item.summary, og_title=item.name, og_description=item.summary, og_image="", canonical_url="", robots="noindex, nofollow", og_type="website", seo_keywords="")


def offering_edit(kind, item_id):
    item = db.session.get(Offering, item_id)
    if item is None or item.kind != kind:
        abort(404)
    return _offering_form(kind, item, f"admin.{kind}s" if kind != "industry" else "admin.industries")


def register(bp):
    from app.admin.routes import permission_required

    def add(rule, view, methods=None, permission=("content.view",)):
        bp.add_url_rule(rule, view_func=permission_required(*permission)(view), methods=methods or ["GET"])

    add("/pages", pages)
    add("/pages/<int:page_id>", page_edit, ["GET", "POST"])
    add("/homepage", homepage, ["GET", "POST"])
    add("/media", media, ["GET", "POST"], ("content.view", "media.manage"))
    add("/navigation", navigation, ["GET", "POST"], ("content.view", "settings.manage"))
    add("/seo", seo, permission=("content.view", "seo.manage"))
    add("/analytics", analytics, permission=("overview",))
    add("/conversions", conversions, permission=("overview",))
    add("/settings", settings, ["GET", "POST"], ("settings.manage",))
    add("/email", email_settings, ["GET", "POST"], ("settings.manage",))
    add("/ask-ai", ask_ai_settings, ["GET", "POST"], ("settings.manage",))
    add("/audit-logs", audit_logs, permission=("audit.view", "users.manage"))
    add("/health", health, permission=("overview",))
    add("/redirects", redirects, ["GET", "POST"], ("settings.manage", "content.edit"))
    add("/backups", backups, permission=("settings.manage",))
    add("/revisions", revisions)
    add("/workflow", workflow)
    add("/search", search, permission=("overview", "content.view", "crm.view"))
    add("/leads/export.csv", leads_export, permission=("leads.export", "crm.edit"))
    add("/preview/offering/<int:item_id>", preview_offering)
    add("/partners", simple_records(Partner, "Partners", "admin.partners", (
        ("name", "Organization", "text"),
        ("relationship", "Relationship type", "text"),
        ("description", "Description", "area"),
        ("website", "Website", "text"),
        ("logo", "Logo", "text"),
        ("evidence", "Approval evidence, internal", "area"),
        ("display", "Display publicly", "bool"),
    ), ("content.edit",)), ["GET", "POST"])
    add("/credentials", simple_records(Credential, "Credentials", "admin.credentials", (
        ("name", "Certification", "text"),
        ("issuer", "Issuer", "text"),
        ("holder", "Holder", "text"),
        ("issued_on", "Issued", "date"),
        ("expires_on", "Expires", "date"),
        ("credential_url", "Credential URL", "text"),
        ("display", "Display publicly", "bool"),
    ), ("content.edit",)), ["GET", "POST"])
    add("/testimonials", simple_records(Testimonial, "Testimonials", "admin.testimonials", (
        ("customer", "Customer", "text"),
        ("company", "Company", "text"),
        ("role", "Role", "text"),
        ("quote", "Quote", "area"),
        ("evidence", "Approval evidence", "area"),
        ("approved", "Customer approval received", "bool"),
        ("status", "Status", "text"),
    ), ("content.edit",)), ["GET", "POST"])

    for kind, slug, title in (
        ("solution", "solutions", "Solutions"),
        ("service", "services", "Services"),
        ("industry", "industries", "Industries"),
    ):
        def list_view(kind=kind, title=title, slug=slug):
            return _offering_list(kind, title, f"admin.{slug}")

        def new_view(kind=kind, slug=slug):
            return _offering_form(kind, Offering(kind=kind, status="draft"), f"admin.{slug}")

        def edit_view(item_id, kind=kind, slug=slug):
            item = db.session.get(Offering, item_id)
            if item is None or item.kind != kind:
                abort(404)
            return _offering_form(kind, item, f"admin.{slug}")

        list_view.__name__ = slug
        new_view.__name__ = f"{slug}_new"
        edit_view.__name__ = f"{slug}_edit"
        add(f"/{slug}", list_view)
        add(f"/{slug}/new", new_view, ["GET", "POST"], ("content.edit",))
        add(f"/{slug}/<int:item_id>", edit_view, ["GET", "POST"])

    bp.add_url_rule("/files/<int:asset_id>/<filename>", view_func=media_file, methods=["GET"])

    @bp.context_processor
    def admin_nav_counts():
        if not getattr(g, "staff", None):
            return {}
        try:
            from app.models import ContactSubmission

            new_count = ContactSubmission.query.filter_by(status="new", archived=False).count()
            open_count = ContactSubmission.query.filter_by(archived=False).count()
            notices = ContactSubmission.query.filter_by(status="new", archived=False).order_by(ContactSubmission.created_at.desc()).limit(5).all()
        except Exception:
            new_count = 0
            open_count = 0
            notices = []
        return {"new_lead_count": new_count, "open_lead_count": open_count, "lead_notices": notices}


def simple_records(model, title, endpoint, fields, permission_edit):
    def view():
        error = ""
        if request.method == "POST":
            if not g.staff.has_any(permission_edit):
                abort(403)
            if request.form.get("delete_id"):
                row = db.session.get(model, request.form.get("delete_id", type=int))
                if row:
                    db.session.delete(row)
                    record_audit("delete", model.__tablename__, "", title)
                    db.session.commit()
                return redirect(url_for(endpoint))
            row_id = request.form.get("row_id", type=int)
            row = db.session.get(model, row_id) if row_id else model()
            for name, _label, kind in fields:
                if kind == "bool":
                    setattr(row, name, request.form.get(name) == "1")
                elif kind == "date":
                    raw = (request.form.get(name) or "").strip()
                    try:
                        setattr(row, name, date.fromisoformat(raw) if raw else None)
                    except ValueError:
                        error = "Use a YYYY-MM-DD date."
                else:
                    raw = (request.form.get(name) or "")[:2000]
                    if name in {"website", "credential_url"}:
                        raw = safe_url(raw)
                    setattr(row, name, raw)
            if model is Testimonial and not (row.status or "").strip():
                row.status = "draft"
            if model is Testimonial and row.status == "published" and not row.approved:
                row.status = "draft"
                error = "Customer approval is required before a testimonial can be published."
            if model is Partner and row.display and not (row.evidence or "").strip():
                row.display = False
                error = "Add internal approval evidence before a relationship can be shown publicly."
            if not error:
                if row.id is None:
                    db.session.add(row)
                record_audit("save", model.__tablename__, getattr(row, "id", ""), title)
                db.session.commit()
                flash(f"{title} saved.")
                return redirect(url_for(endpoint))
        rows = model.query.order_by(model.id.desc()).all()
        return _render("admin/records.html", title=title, rows=rows, fields=fields, error=error, endpoint=endpoint)

    view.__name__ = endpoint.replace("admin.", "")
    return view
