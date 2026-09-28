import logging
import os
import re

from flask import current_app, flash, request, url_for

from app.models import PageSeo


_BLOCK_TAGS = re.compile(
    r"<\s*(script|iframe|object|embed|link|meta|base|form)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_VOID_DANGEROUS = re.compile(
    r"<\s*(script|iframe|object|embed|link|meta|base)\b[^>]*/?\s*>",
    re.IGNORECASE,
)
_EVENT_ATTRS = re.compile(r"\s+on\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URLS = re.compile(
    r"\s+(href|src|action)\s*=\s*([\"'])\s*javascript:[^\"']*\2",
    re.IGNORECASE,
)


def sanitize_html(value):
    text = value or ""
    text = _BLOCK_TAGS.sub("", text)
    text = _VOID_DANGEROUS.sub("", text)
    text = _EVENT_ATTRS.sub("", text)
    text = _JS_URLS.sub("", text)
    return text


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:200]


def canonical_url(path):
    base = current_app.config["SITE_URL"].rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def absolute_static(filename):
    if not filename:
        return ""
    if filename.startswith("http://") or filename.startswith("https://"):
        return filename
    return canonical_url(url_for("static", filename=filename.lstrip("/")))


def seo_for(page_key, title, description, image=""):
    record = db_seo(page_key)
    seo_title = (record.seo_title if record and record.seo_title else title)
    meta = (record.meta_description if record and record.meta_description else description)
    og = (record.og_image if record and record.og_image else image)
    return {
        "seo_title": seo_title,
        "meta_description": meta,
        "og_title": seo_title,
        "og_description": meta,
        "og_image": absolute_static(og) if og else "",
        "canonical_url": canonical_url(request.path),
        "robots": "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1",
        "og_type": "website",
        "seo_keywords": "",
    }


def db_seo(page_key):
    try:
        return PageSeo.query.filter_by(page_key=page_key).first()
    except Exception:
        current_app.logger.debug("SEO lookup skipped for %s", page_key)
        return None


def configure_logging(app):
    if app.testing:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    app.logger.setLevel(logging.INFO)
    if not app.logger.handlers:
        app.logger.addHandler(handler)
    os.makedirs(app.instance_path, exist_ok=True)


def flash_errors(errors):
    for error in errors:
        flash(error, "error")
