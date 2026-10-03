"""Public content images: upload, display size, and corner radius."""

import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from app.services import file_signature_ok, safe_static_path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def image_pixels(value, default, upper):
    if value is None or str(value).strip() == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(number, upper))


def managed_image_style(width=0, height=0, radius=24):
    """Inline style so an admin-chosen size and radius win over the theme."""
    width = image_pixels(width, 0, 2400)
    height = image_pixels(height, 0, 1600)
    radius = image_pixels(radius, 24, 80)
    parts = [
        f"border-radius:{radius}px",
        "max-width:100%",
        "object-fit:cover",
        "display:block",
    ]
    parts.append(f"width:{width}px" if width else "width:100%")
    if height:
        parts.append(f"height:{height}px")
    return ";".join(parts)


def save_public_image(upload):
    """Store an uploaded image where the public site can serve it. Returns (path, error)."""
    filename = secure_filename(upload.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    header = upload.stream.read(16)
    upload.stream.seek(0)
    if ext not in IMAGE_EXTENSIONS or not file_signature_ok(ext, header):
        return "", "Use a PNG, JPG, WEBP, or GIF image."
    stored = f"uploads/{uuid.uuid4().hex}{ext}"
    directory = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(directory, exist_ok=True)
    upload.save(os.path.join(directory, os.path.basename(stored)))
    return stored, ""


def apply_managed_image(record, path_attr, file_name, width_attr, height_attr, radius_attr):
    """Save an upload or the existing path, plus width, height, and radius, on the record."""
    from flask import request

    upload = request.files.get(file_name) if request.files else None
    if upload is not None and upload.filename:
        stored, error = save_public_image(upload)
        if error:
            return error
        setattr(record, path_attr, stored)
    else:
        posted = request.form.get(path_attr)
        current = posted if posted is not None else getattr(record, path_attr, "")
        setattr(record, path_attr, safe_static_path(current))
    setattr(record, width_attr, image_pixels(request.form.get(width_attr), 0, 2400))
    setattr(record, height_attr, image_pixels(request.form.get(height_attr), 0, 1600))
    current_radius = getattr(record, radius_attr, 24)
    setattr(record, radius_attr, image_pixels(request.form.get(radius_attr), current_radius if current_radius is not None else 24, 80))
    return ""
