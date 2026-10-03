import json

from flask import g, request

from app.extensions import db
from app.models import Category
from app.models.platform import (
    AuditLog,
    ContentRevision,
    ConversionEvent,
    HomeSection,
    NavItem,
    Offering,
    SitePage,
    SiteSetting,
)

PAGES = (
    ("home", "Home", "/"),
    ("about", "About", "/about"),
    ("solutions", "Solutions", "/solutions"),
    ("services", "Services", "/services"),
    ("industries", "Industries", "/industries"),
    ("case-studies", "Case Studies", "/case-studies"),
    ("insights", "Insights", "/insights"),
    ("careers", "Careers", "/careers"),
    ("contact", "Contact", "/contact"),
    ("privacy", "Privacy Policy", "/privacy-policy"),
    ("terms", "Terms of Service", "/terms-of-service"),
    ("cookies", "Cookie Policy", "/cookie-policy"),
    ("responsible-ai", "Responsible AI", "/responsible-ai"),
    ("ai-security", "AI Security", "/ai-security"),
)

HOME_SECTIONS = (
    ("hero", "Hero"),
    ("about", "About Neural Xpert"),
    ("capabilities", "Enterprise AI Capabilities"),
    ("services", "Services"),
    ("process", "Work Process"),
    ("studies", "Case Studies"),
    ("ecosystem", "Technology Ecosystem"),
    ("why", "Why Neural Xpert"),
    ("industries", "Industries"),
    ("integrations", "Integrations"),
    ("engagement", "Engagement Models"),
    ("testimonials", "Testimonials"),
    ("cta", "Main CTA"),
    ("insights", "Insights"),
)

OFFERINGS = (
    ("solution", "Generative AI", "generative-ai"),
    ("solution", "AI Agents", "ai-agents"),
    ("solution", "Enterprise RAG", "enterprise-rag"),
    ("solution", "Machine Learning", "machine-learning"),
    ("solution", "Intelligent Automation", "intelligent-automation"),
    ("solution", "AI Security & Governance", "ai-security"),
    ("service", "AI Strategy & Consulting", "ai-strategy"),
    ("service", "AI Engineering & Development", "ai-engineering"),
    ("service", "Cloud & AI Infrastructure", "cloud-infrastructure"),
    ("service", "Cybersecurity", "cybersecurity"),
    ("service", "Data & Integration", "data-integration"),
    ("service", "MLOps & AI Operations", "mlops"),
    ("industry", "Financial Services", "financial-services"),
    ("industry", "Telecommunications", "telecommunications"),
    ("industry", "Government & Public Sector", "government"),
    ("industry", "Healthcare", "healthcare"),
    ("industry", "Retail & Commerce", "retail"),
    ("industry", "Technology", "technology"),
    ("industry", "Logistics", "logistics"),
)

NAV = (
    ("header", "Home", "/"),
    ("header", "About", "/about"),
    ("header", "Solutions", "/solutions"),
    ("header", "Services", "/services"),
    ("header", "Industries", "/industries"),
    ("header", "Case Studies", "/case-studies"),
    ("header", "Insights", "/insights"),
    ("header", "Careers", "/careers"),
    ("header", "Contact", "/contact"),
    ("footer", "Privacy Policy", "/privacy-policy"),
    ("footer", "Terms of Service", "/terms-of-service"),
    ("footer", "Cookie Policy", "/cookie-policy"),
    ("footer", "Contact", "/contact"),
)

ARTICLE_CATEGORIES = (
    "Generative AI",
    "AI Agents",
    "Enterprise RAG",
    "Machine Learning",
    "MLOps",
    "AI Security",
    "Cybersecurity",
    "Cloud",
    "Data & Analytics",
    "Enterprise Integration",
)

SETTING_KEYS = (
    "company_name",
    "contact_email",
    "phone",
    "address",
    "footer_text",
    "copyright",
    "primary_cta_label",
    "primary_cta_url",
    "default_seo_image",
    "analytics_id",
    "social_linkedin",
    "social_x",
    "logo_public",
    "logo_footer",
    "logo_icon",
    "logo_favicon",
    "logo_admin",
    "mail_server",
    "mail_port",
    "mail_use_tls",
    "mail_use_ssl",
    "mail_username",
    "mail_password",
    "mail_sender",
    "mail_recipient",
    "mail_contact_subject",
    "mail_contact_body",
    "mail_career_subject",
    "mail_career_body",
)

LIVE_PAGE_KEYS = {"home", "about", "solutions", "services", "industries", "case-studies", "insights", "careers", "contact", "privacy", "terms", "cookies"}


def ensure_catalog():
    for key, title, slug in PAGES:
        if SitePage.query.filter_by(key=key).first() is None:
            db.session.add(
                SitePage(
                    key=key,
                    title=title,
                    slug=slug,
                    status="published" if key in LIVE_PAGE_KEYS else "draft",
                )
            )
    for index, (key, name) in enumerate(HOME_SECTIONS, start=1):
        if HomeSection.query.filter_by(key=key).first() is None:
            db.session.add(HomeSection(key=key, name=name, position=index, enabled=True))
    for index, (kind, name, slug) in enumerate(OFFERINGS, start=1):
        if Offering.query.filter_by(kind=kind, slug=slug).first() is None:
            db.session.add(Offering(kind=kind, name=name, slug=slug, position=index, status="draft"))
    for index, (menu, label, url) in enumerate(NAV, start=1):
        if NavItem.query.filter_by(menu=menu, label=label).first() is None:
            db.session.add(NavItem(menu=menu, label=label, url=url, position=index, enabled=False))
    for name in ARTICLE_CATEGORIES:
        slug = name.lower().replace(" & ", "-").replace(" ", "-")
        if Category.query.filter_by(slug=slug, kind="article").first() is None:
            db.session.add(Category(name=name, slug=slug, kind="article"))
    for key in SETTING_KEYS:
        if SiteSetting.query.filter_by(key=key).first() is None:
            db.session.add(SiteSetting(key=key, value=""))
    db.session.commit()


def record_security(action, detail="", staff=None):
    """Write a security event even when no staff session exists yet."""
    from flask import current_app

    try:
        db.session.add(
            AuditLog(
                staff_id=staff.id if staff else None,
                action=(action or "")[:80],
                object_type="security",
                object_id="",
                detail=(detail or "")[:400],
                ip_address=(request.remote_addr or "")[:64] if request else "",
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning("Security event %s was not stored", action)
    current_app.logger.warning("security %s %s", action, detail or "")


def record_audit(action, object_type="", object_id="", detail=""):
    staff = getattr(g, "staff", None)
    db.session.add(
        AuditLog(
            staff_id=staff.id if staff else None,
            action=action[:80],
            object_type=(object_type or "")[:40],
            object_id=str(object_id or "")[:40],
            detail=(detail or "")[:4000],
            ip_address=(request.remote_addr or "")[:64] if request else "",
        )
    )


def record_revision(obj, note=""):
    data = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        data[column.name] = value.isoformat() if hasattr(value, "isoformat") else value
    staff = getattr(g, "staff", None)
    db.session.add(
        ContentRevision(
            object_type=obj.__tablename__[:40],
            object_id=obj.id or 0,
            note=(note or "")[:255],
            snapshot=json.dumps(data, default=str)[:20000],
            staff_id=staff.id if staff else None,
        )
    )


def record_event(name, path="", label=""):
    db.session.add(ConversionEvent(name=name[:80], path=(path or "")[:300], label=(label or "")[:255]))


def seo_checks(title, description, h1, image_alt=True, links=True, canonical=True):
    checks = [
        ("SEO title", bool(title and 15 <= len(title) <= 70)),
        ("Meta description", bool(description and 50 <= len(description) <= 180)),
        ("H1", bool(h1)),
        ("Image ALT", bool(image_alt)),
        ("Internal links", bool(links)),
        ("Canonical", bool(canonical)),
    ]
    missing = [name for name, ok in checks if not ok]
    if not missing:
        grade = "Good"
    elif len(missing) <= 2:
        grade = "Needs improvement"
    else:
        grade = "Critical"
    return grade, checks


def setting_value(key):
    row = SiteSetting.query.filter_by(key=key).first()
    return (row.value or "").strip() if row else ""
