import os
import secrets
from xml.sax.saxutils import escape

import click
from flask import Flask, abort, g, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import csrf, db, limiter, mail, migrate
from app.services import configure_logging, plain_excerpt, safe_local_path, safe_static_path, safe_url, sanitize_html, seo_for
from config import CONFIGS


def _require_production_secrets(app):
    secret = app.config.get("SECRET_KEY") or ""
    weak_secrets = {"", "dev-only-change-me", "change-me", "test-secret"}
    database_url = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if secret in weak_secrets or len(secret) < 32:
        raise RuntimeError("Set a unique SECRET_KEY of at least 32 characters before production.")
    if not database_url.startswith("postgresql") or "neuralxpert:neuralxpert@" in database_url:
        raise RuntimeError("Set DATABASE_URL to the production PostgreSQL URL (postgresql+psycopg://).")


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(CONFIGS[config_name])
    if config_name == "production":
        _require_production_secrets(app)
    elif config_name != "testing":
        secret = app.config.get("SECRET_KEY") or ""
        if secret in {"", "dev-only-change-me", "change-me", "test-secret"} or len(secret) < 32:
            app.logger.warning("SECRET_KEY is still a development placeholder. Set a unique value before this server is reachable.")
    app.url_map.strict_slashes = False
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrations_dir = os.path.abspath(os.path.join(app.root_path, os.pardir, "migrations"))
    migrate.init_app(app, db, directory=migrations_dir)
    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    configure_logging(app)
    app.jinja_env.filters["sanitize_html"] = sanitize_html
    app.jinja_env.filters["plain_excerpt"] = plain_excerpt
    app.jinja_env.filters["safe_url"] = safe_url
    app.jinja_env.filters["safe_static"] = safe_static_path
    from app.images import managed_image_style

    app.jinja_env.filters["managed_image_style"] = managed_image_style

    from app import models  # noqa: F401
    from app.admin.routes import bp as admin_bp
    from app.blog.routes import bp as blog_bp
    from app.careers.routes import bp as careers_bp
    from app.case_studies.routes import bp as case_studies_bp
    from app.contact.routes import bp as contact_bp
    from app.main.routes import bp as main_bp
    from app.visitors import record_public_visit

    if config_name == "development" and not app.config.get("MAIL_SERVER"):
        app.config["ADMIN_OTP_ON_PAGE"] = True
        app.logger.warning("SMTP is not configured, so admin sign-in codes are shown on the verify page. Do not expose this server.")

    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    @app.route("/brand/<path:name>")
    def brand_file(name):
        from app.brand import send_brand

        return send_brand(name)

    app.register_blueprint(blog_bp)
    app.register_blueprint(case_studies_bp)
    app.register_blueprint(careers_bp)
    app.register_blueprint(contact_bp)

    if config_name == "production":
        # Trust one proxy for the client IP and scheme. Do not trust X-Forwarded-Host from the client.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)

    @app.context_processor
    def defaults():
        from app.models import Article

        sidebar_posts = []
        try:
            sidebar_posts = (
                Article.query.filter_by(status="published")
                .order_by(Article.published_at.desc(), Article.id.desc())
                .limit(3)
                .all()
            )
        except Exception:
            app.logger.warning("Sidebar articles are unavailable", exc_info=True)
        header_nav = []
        footer_nav = []
        try:
            from app.models.platform import NavItem

            header_nav = NavItem.query.filter_by(menu="header", enabled=True).order_by(NavItem.position, NavItem.id).all()
            footer_nav = NavItem.query.filter_by(menu="footer", enabled=True).order_by(NavItem.position, NavItem.id).all()
        except Exception:
            app.logger.warning("Navigation records are unavailable", exc_info=True)
        public_testimonials = []
        public_partners = []
        public_credentials = []
        try:
            from datetime import date

            from app.models.platform import Credential, Partner, Testimonial

            public_testimonials = (
                Testimonial.query.filter_by(status="published", approved=True)
                .order_by(Testimonial.id.desc())
                .limit(6)
                .all()
            )
            public_partners = [
                row
                for row in Partner.query.filter_by(display=True).order_by(Partner.position, Partner.id).all()
                if (row.evidence or "").strip()
            ]
            today = date.today()
            public_credentials = [
                row
                for row in Credential.query.filter_by(display=True, status="active").order_by(Credential.name).all()
                if row.expires_on is None or row.expires_on >= today
            ]
        except Exception:
            app.logger.warning("Public trust records are unavailable", exc_info=True)
        return {
            "footer_variant": "inner",
            "seo_title": "Neural Xpert",
            "meta_description": "Neural Xpert builds secure enterprise AI solutions.",
            "og_title": "",
            "og_description": "",
            "og_image": "",
            "canonical_url": request.base_url,
            "robots": "index, follow",
            "og_type": "website",
            "seo_keywords": "",
            "sidebar_posts": sidebar_posts,
            "header_nav": header_nav,
            "footer_nav": footer_nav,
            "public_testimonials": public_testimonials,
            "public_partners": public_partners,
            "public_credentials": public_credentials,
            "ask_ai": _ask_ai(),
            "brand": _brand(),
            "csp_nonce": getattr(g, "csp_nonce", ""),
        }

    @app.template_global()
    def home_on(key):
        sections = _home_sections()
        row = sections.get(key)
        return True if row is None else bool(row.enabled)

    @app.template_global()
    def home_order(key):
        sections = _home_sections()
        row = sections.get(key)
        if row is not None:
            return row.position
        from app.admin.catalog import HOME_SECTIONS

        order = {item: index for index, (item, _name) in enumerate(HOME_SECTIONS, start=1)}
        return order.get(key, 50)

    @app.template_global()
    def home_text(key, field):
        row = _home_sections().get(key)
        if row is None:
            return ""
        return (getattr(row, field, "") or "").strip()

    def _brand():
        from flask import url_for

        try:
            from app.brand import brand_urls

            return brand_urls()
        except Exception:
            app.logger.warning("Brand logos are unavailable", exc_info=True)
            logo = url_for("static", filename="img/logo-neural-xpert.png")
            return {
                "header": logo,
                "footer": logo,
                "icon": url_for("static", filename="img/logo-icon.png"),
                "admin": logo,
                "favicon": url_for("static", filename="img/favicons/favicon-32x32.png"),
                "favicon_custom": False,
            }

    def _ask_ai():
        try:
            from app.ai_support import widget_state

            return widget_state()
        except Exception:
            app.logger.warning("Ask AI settings are unavailable", exc_info=True)
            return {"enabled": False, "label": "ASK AI", "welcome": ""}

    def _home_sections():
        from flask import g

        if not hasattr(g, "home_section_map"):
            try:
                from app.models.platform import HomeSection

                g.home_section_map = {row.key: row for row in HomeSection.query.all()}
            except Exception:
                g.home_section_map = {}
        return g.home_section_map

    @app.before_request
    def assign_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def apply_redirects():
        if request.path.startswith(("/admin", "/static")):
            return None
        try:
            from app.models.platform import RedirectRule

            rule = RedirectRule.query.filter_by(source=request.path, enabled=True).first()
        except Exception:
            return None
        if rule:
            target = safe_local_path(rule.target)
            code = 301 if rule.status_code not in {301, 302} else rule.status_code
            if target:
                return redirect(target, code=code)
            app.logger.warning("Ignored redirect %s because the destination is not a local path", rule.source)
        return None

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        nonce = getattr(g, "csp_nonce", "") or secrets.token_urlsafe(16)
        policy = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "object-src 'none'; "
            "frame-src 'self'; "
            "frame-ancestors 'self'; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if config_name == "production":
            policy += "; upgrade-insecure-requests"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.path.startswith("/brand/") and request.path.endswith(".svg"):
            policy = "default-src 'none'; sandbox"
            response.headers["Content-Disposition"] = "attachment"
        response.headers["Content-Security-Policy"] = policy
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        return record_public_visit(response)

    @app.errorhandler(404)
    def not_found(_error):
        context = seo_for("error", "Page not found | Neural Xpert", "The page you requested could not be found.")
        context["robots"] = "noindex, follow"
        return render_template("main/error.html", **context), 404

    @app.errorhandler(500)
    def server_error(_error):
        app.logger.exception("Unhandled application error")
        if app.debug:
            raise
        return "Something went wrong. Please try again later.", 500

    @app.route("/robots.txt")
    def robots():
        body = (
            "User-agent: *\nAllow: /\nDisallow: /admin\n"
            f"Sitemap: {app.config['SITE_URL'].rstrip('/')}/sitemap.xml\n"
        )
        return body, 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.route("/sitemap.xml")
    def sitemap():
        from app.models import Article, CaseStudy, Job

        urls = [
            url_for("main.index"),
            url_for("main.about"),
            url_for("main.solutions"),
            url_for("main.services"),
            url_for("main.industries"),
            url_for("case_studies.index"),
            url_for("blog.index"),
            url_for("careers.index"),
            url_for("contact.index"),
            url_for("main.privacy_policy"),
            url_for("main.terms_of_service"),
            url_for("main.cookie_policy"),
        ]
        for article in Article.query.filter_by(status="published").all():
            urls.append(url_for("blog.detail", slug=article.slug))
        for study in CaseStudy.query.filter_by(status="published").all():
            urls.append(url_for("case_studies.detail", slug=study.slug))
        for job in Job.query.filter(Job.status.in_(("published", "open"))).all():
            urls.append(url_for("careers.detail", slug=job.slug))
        base = app.config["SITE_URL"].rstrip("/")
        items = "\n".join(f"  <url><loc>{escape(base + path)}</loc></url>" for path in urls)
        xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'
        return xml, 200, {"Content-Type": "application/xml; charset=utf-8"}

    legacy = {
        "index.html": "main.index",
        "about.html": "main.about",
        "features.html": "main.solutions",
        "case-studies.html": "case_studies.index",
        "case-studies-2.html": "case_studies.index",
        "case-studies-details.html": "case_studies.index",
        "blog.html": "blog.index",
        "blog-details.html": "blog.index",
        "careers.html": "careers.index",
        "contact.html": "contact.index",
        "privacy-policy.html": "main.privacy_policy",
        "terms-of-service.html": "main.terms_of_service",
        "cookie-policy.html": "main.cookie_policy",
        "home-ai-startup.html": "main.index",
    }

    @app.route("/<path:legacy_path>")
    def legacy_redirect(legacy_path):
        if legacy_path == "blog-rathat.html":
            return redirect(url_for("blog.detail", slug="rathat-android-trojan-uses-ai-for-automation"), 301)
        endpoint = legacy.get(legacy_path)
        if endpoint:
            return redirect(url_for(endpoint), 301)
        abort(404)

    @app.cli.command("seed")
    def seed_command():
        from app.seed import seed

        seed()
        print("Seed data is ready.")

    @app.cli.command("create-staff")
    @click.argument("email")
    def create_staff_command(email):
        """Create an internal staff account and print a one-time password."""
        from app.admin.security import create_staff

        try:
            staff, password = create_staff(email)
        except ValueError as exc:
            raise SystemExit(str(exc))
        print(f"Staff account created for {staff.email}")
        print(f"Temporary password: {password}")
        print("Sign in at /admin/login. This password is shown only once.")

    return app
