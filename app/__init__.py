import os

from flask import Flask, abort, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import csrf, db, limiter, mail, migrate
from app.services import configure_logging, sanitize_html, seo_for
from config import CONFIGS


def _require_production_secrets(app):
    secret = app.config.get("SECRET_KEY") or ""
    weak_secrets = {"", "dev-only-change-me", "change-me", "test-secret"}
    database_url = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if secret in weak_secrets or len(secret) < 32:
        raise RuntimeError("Set a unique SECRET_KEY of at least 32 characters before production.")
    if database_url.startswith("sqlite") or "neuralxpert:neuralxpert@" in database_url:
        raise RuntimeError("Set DATABASE_URL to the production PostgreSQL database.")


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(CONFIGS[config_name])
    if config_name == "production":
        _require_production_secrets(app)
    app.url_map.strict_slashes = False
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    configure_logging(app)
    app.jinja_env.filters["sanitize_html"] = sanitize_html

    from app import models  # noqa: F401
    from app.blog.routes import bp as blog_bp
    from app.careers.routes import bp as careers_bp
    from app.case_studies.routes import bp as case_studies_bp
    from app.contact.routes import bp as contact_bp
    from app.main.routes import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(case_studies_bp)
    app.register_blueprint(careers_bp)
    app.register_blueprint(contact_bp)

    if config_name == "production":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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
            app.logger.debug("Sidebar articles are unavailable")
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
        }

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline'; "
            "frame-src 'none'; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if config_name == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

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
        body = f"User-agent: *\nAllow: /\nSitemap: {app.config['SITE_URL'].rstrip('/')}/sitemap.xml\n"
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
        for job in Job.query.filter_by(status="published").all():
            urls.append(url_for("careers.detail", slug=job.slug))
        base = app.config["SITE_URL"].rstrip("/")
        items = "\n".join(f"  <url><loc>{base}{path}</loc></url>" for path in urls)
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

    return app
