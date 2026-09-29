"""Public and admin logos. An empty setting keeps the designed artwork."""

import os
import re
import uuid

from flask import abort, current_app, send_from_directory, url_for
from werkzeug.utils import secure_filename

STORED = re.compile(r"logos/[a-f0-9]{32}\.(png|jpg|jpeg|webp|gif|svg|ico)")
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}
MAX_BYTES = 2_000_000

LOGO_SLOTS = (
    ("logo_public", "Public header and mobile menu", "Shown in the navbar on every public page.", "img/logo-neural-xpert.png"),
    ("logo_footer", "Public footer", "Leave empty to use the public header logo.", "img/logo-neural-xpert.png"),
    ("logo_icon", "Homepage mark", "The small mark in the homepage scroll badge.", "img/logo-icon.png"),
    ("logo_favicon", "Browser icon", "Replaces the favicon in the browser tab.", "img/favicons/favicon-32x32.png"),
    ("logo_admin", "Admin logo", "Shown on the admin bar and the sign-in page. Leave empty to use the public header logo.", "img/logo-neural-xpert.png"),
)


def brand_urls():
    from app.admin.catalog import setting_value

    public = setting_value("logo_public")
    footer = setting_value("logo_footer") or public
    icon = setting_value("logo_icon")
    favicon = setting_value("logo_favicon")
    admin = setting_value("logo_admin") or public
    return {
        "header": _url(public, "img/logo-neural-xpert.png"),
        "footer": _url(footer, "img/logo-neural-xpert.png"),
        "icon": _url(icon, "img/logo-icon.png"),
        "admin": _url(admin, "img/logo-neural-xpert.png"),
        "favicon": _url(favicon, "img/favicons/favicon-32x32.png"),
        "favicon_custom": bool(favicon and STORED.fullmatch(favicon)),
    }


def logo_slots():
    from app.admin.catalog import setting_value

    urls = brand_urls()
    preview = {
        "logo_public": urls["header"],
        "logo_footer": urls["footer"],
        "logo_icon": urls["icon"],
        "logo_favicon": urls["favicon"],
        "logo_admin": urls["admin"],
    }
    return [
        {
            "key": key,
            "label": label,
            "help": help_text,
            "preview": preview[key],
            "custom": bool(STORED.fullmatch(setting_value(key) or "")),
        }
        for key, label, help_text, _default in LOGO_SLOTS
    ]


def _upload_root():
    folder = current_app.config["UPLOAD_FOLDER"]
    if not os.path.isabs(folder):
        folder = os.path.join(os.path.dirname(current_app.root_path), folder)
    return folder


def store_logo(upload):
    filename = secure_filename(upload.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in EXTENSIONS:
        return "", "Use a PNG, JPG, WEBP, GIF, SVG, or ICO file."
    stored = f"logos/{uuid.uuid4().hex}{ext}"
    directory = os.path.join(_upload_root(), "logos")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(_upload_root(), stored)
    upload.save(path)
    if os.path.getsize(path) > MAX_BYTES:
        os.remove(path)
        return "", "Each logo must be under 2 MB."
    return stored, ""


def remove_stored(value):
    if not value or not STORED.fullmatch(value):
        return
    path = os.path.join(_upload_root(), value)
    if os.path.isfile(path):
        os.remove(path)


def send_brand(name):
    if not STORED.fullmatch(name or ""):
        abort(404)
    directory = os.path.join(_upload_root(), "logos")
    return send_from_directory(directory, os.path.basename(name))


def _url(value, default):
    if value and STORED.fullmatch(value):
        return url_for("brand_file", name=value)
    return url_for("static", filename=default)
