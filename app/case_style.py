"""Appearance of the public case-studies page: type, size, and color."""

import re

from app.images import apply_managed_image, image_pixels

FONT_CHOICES = (
    ("", "Theme default"),
    ("sora", "Sora"),
    ("work-sans", "Work Sans"),
    ("georgia", "Georgia"),
    ("arial", "Arial"),
    ("times", "Times New Roman"),
)

FONT_CSS = {
    "sora": '"Sora", sans-serif',
    "work-sans": '"Work Sans", sans-serif',
    "georgia": "Georgia, serif",
    "arial": "Arial, Helvetica, sans-serif",
    "times": '"Times New Roman", Times, serif',
}

_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")


def clean_font(value):
    return value if value in FONT_CSS else ""


def clean_color(value):
    raw = (value or "").strip()
    return raw.lower() if _COLOR.fullmatch(raw) else ""


def apply_page_style(page):
    """Write the listing copy and type settings from the current form."""
    from flask import request

    page.title = (request.form.get("title") or page.title or "Case studies").strip()[:255]
    page.hero_title = (request.form.get("hero_title") or "")[:255]
    page.hero_subtitle = (request.form.get("hero_subtitle") or "")[:2000]
    page.summary = (request.form.get("summary") or "")[:5000]
    page.cta_label = (request.form.get("cta_label") or "")[:120]
    page.font_family = clean_font(request.form.get("font_family"))
    page.heading_size = image_pixels(request.form.get("heading_size"), 0, 96)
    page.body_size = image_pixels(request.form.get("body_size"), 0, 40)
    page.tag_size = image_pixels(request.form.get("tag_size"), 0, 32)
    page.heading_color = clean_color(request.form.get("heading_color"))
    page.body_color = clean_color(request.form.get("body_color"))
    return apply_managed_image(page, "hero_image", "hero_image_file", "hero_width", "hero_height", "hero_radius")


def apply_card_type(study):
    from flask import request

    study.font_family = clean_font(request.form.get("font_family"))
    study.title_size = image_pixels(request.form.get("title_size"), 0, 96)
    study.summary_size = image_pixels(request.form.get("summary_size"), 0, 40)


def page_css(page):
    """CSS variables for the listing and detail pages. Empty values keep the theme."""
    if page is None:
        return ""
    parts = []
    family = FONT_CSS.get(page.font_family or "")
    if family:
        parts.append(f"--nx-case-font:{family}")
        parts.append(f"--nx-case-title-font:{family}")
    if page.heading_size:
        parts.append(f"--nx-case-heading-size:{int(page.heading_size)}px")
    if page.body_size:
        parts.append(f"--nx-case-body-size:{int(page.body_size)}px")
    if page.tag_size:
        parts.append(f"--nx-case-tag-size:{int(page.tag_size)}px")
    if page.heading_color:
        parts.append(f"--nx-case-heading-color:{page.heading_color}")
    if page.body_color:
        parts.append(f"--nx-case-body-color:{page.body_color}")
    if page.hero_width:
        parts.append(f"--nx-case-hero-width:{int(page.hero_width)}px")
    if page.hero_height:
        parts.append(f"--nx-case-hero-height:{int(page.hero_height)}px")
    if page.hero_image and page.hero_radius:
        parts.append(f"--nx-case-hero-radius:{int(page.hero_radius)}px")
    return ";".join(parts)


def banner_style(width, height, radius):
    """Size a background hero only when the admin has chosen a size or a non-default radius."""
    width = int(width or 0)
    height = int(height or 0)
    radius = int(radius if radius is not None else 24)
    parts = []
    if width:
        parts.extend((f"width:{width}px", "max-width:100%", "margin-inline:auto"))
    if height:
        parts.append(f"min-height:{height}px")
    if radius != 24:
        parts.extend((f"border-radius:{radius}px", "overflow:hidden"))
    return ";".join(parts)


def card_text_style(study, kind):
    parts = []
    family = FONT_CSS.get(getattr(study, "font_family", "") or "")
    if family:
        parts.append(f"font-family:{family}")
    sizes = {"title": study.title_size, "summary": study.summary_size}
    size = sizes.get(kind) or 0
    if size:
        parts.append(f"font-size:{int(size)}px")
    return ";".join(parts)
