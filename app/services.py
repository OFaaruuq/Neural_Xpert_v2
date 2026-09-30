import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from flask import current_app, flash, request, url_for

from app.models import PageSeo


_ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li",
    "h2", "h3", "h4", "blockquote", "a", "code", "pre", "span", "div",
    "hr", "table", "thead", "tbody", "tr", "th", "td", "img",
    "figure", "figcaption", "sup", "sub",
}
_VOID_TAGS = {"br", "hr", "img"}
_DROP_TAGS = {"script", "style", "iframe", "object", "embed", "link", "meta", "base", "form", "svg", "math", "template"}
_URL_ATTRS = {"href", "src"}
_CLASS_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_STATIC_PATH = re.compile(r"^[A-Za-z0-9_./-]+$")


def plain_excerpt(value, limit=220):
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip(".,;:") + "…"


def safe_url(value):
    """Allow site-relative links and http(s)/mailto targets. Reject scripts and protocol-relative URLs."""
    raw = (value or "").replace("\\", "").strip()
    if not raw or any(char in raw for char in "\r\n\t"):
        return ""
    lowered = raw.lower()
    if lowered.startswith(("javascript:", "data:", "vbscript:", "file:")):
        return ""
    if raw.startswith("//"):
        return ""
    if raw.startswith(("#", "?")) or (raw.startswith("/") and not raw.startswith("//")):
        return raw[:500]
    if lowered.startswith("mailto:"):
        address = raw[7:].split("?", 1)[0]
        if re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", address):
            return raw[:500]
        return ""
    parts = urlsplit(raw)
    if parts.scheme in {"http", "https"} and parts.netloc and parts.username is None:
        return raw[:500]
    return ""


def safe_local_path(value):
    """A same-site path used for redirects. External and protocol-relative targets are rejected."""
    raw = safe_url(value)
    if not raw.startswith("/") or raw.startswith("//"):
        return ""
    return raw


def safe_static_path(value):
    raw = (value or "").strip().lstrip("/")
    if not raw or ".." in raw.split("/") or not _STATIC_PATH.fullmatch(raw):
        return ""
    if raw.startswith(("/", "\\")) or "://" in raw:
        return ""
    return raw[:500]


def file_signature_ok(extension, header):
    extension = (extension or "").lower()
    header = header or b""
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    if extension == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if extension == ".pdf":
        return header.startswith(b"%PDF")
    if extension == ".ico":
        return header.startswith(b"\x00\x00\x01\x00") or header.startswith(b"\x89PNG")
    if extension == ".doc":
        return header.startswith(b"\xd0\xcf\x11\xe0")
    if extension == ".docx":
        return header.startswith(b"PK")
    return False


class _HtmlSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def _start(self, tag, attrs, closing):
        tag = (tag or "").lower()
        if tag in _DROP_TAGS or tag not in _ALLOWED_TAGS:
            return
        rendered = []
        for name, value in attrs:
            name = (name or "").lower()
            if not name or name.startswith("on") or name in {"style", "srcset", "formaction"}:
                continue
            value = value or ""
            if name == "class":
                classes = " ".join(part for part in value.split() if _CLASS_NAME.fullmatch(part))
                if classes:
                    rendered.append(("class", classes))
                continue
            if name in _URL_ATTRS:
                cleaned = safe_url(value)
                if not cleaned:
                    continue
                rendered.append((name, cleaned))
                continue
            if tag in {"td", "th"} and name in {"colspan", "rowspan"} and value.isdigit() and int(value) <= 12:
                rendered.append((name, value))
            elif tag == "img" and name == "alt":
                rendered.append((name, value[:300]))
            elif name == "title" and tag in {"a", "img"}:
                rendered.append((name, value[:300]))
        attributes = "".join(
            f' {escape(name, quote=True)}="{escape(item, quote=True)}"' for name, item in rendered
        )
        self.parts.append(f"<{tag}{attributes}>")
        if tag not in _VOID_TAGS and not closing:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        if tag in self._stack:
            while self._stack:
                opened = self._stack.pop()
                self.parts.append(f"</{opened}>")
                if opened == tag:
                    break

    def handle_data(self, data):
        if data:
            self.parts.append(escape(data))

    def close(self):
        super().close()
        while self._stack:
            self.parts.append(f"</{self._stack.pop()}>")
        return "".join(self.parts)


def sanitize_html(value):
    parser = _HtmlSanitizer()
    try:
        parser.feed(value or "")
        return parser.close()
    except Exception:
        current_app.logger.warning("HTML content was rejected because it could not be parsed")
        return escape(value or "")


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
