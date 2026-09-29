from datetime import timedelta

from flask import request, url_for
from sqlalchemy import func

from app.admin.catalog import seo_checks
from app.extensions import db
from app.models import Article, CaseStudy, ContactSubmission, DailyPageView, DailyVisitor, Offering, SitePage
from app.models.platform import ConversionEvent
from app.visitors import _today


def load_board():
    days = request.args.get("days", type=int)
    if days not in (7, 30):
        days = 30
    today = _today()
    start = today - timedelta(days=days - 1)
    prior = start - timedelta(days=days)
    series = _daily_series(start, today)
    views_now = _view_total(start, today)
    views_prior = _view_total(prior, start - timedelta(days=1))
    leads = ContactSubmission.query.filter_by(archived=False).all()
    recent_leads = sorted(leads, key=lambda row: row.created_at.isoformat() if row.created_at else "", reverse=True)[:5]
    return {
        "kpis": _kpis(),
        "chart": _chart(series),
        "views_total": _comma(views_now),
        "views_delta": _pct(views_now, views_prior),
        "visitors_today": int(
            db.session.query(func.count(func.distinct(DailyVisitor.visitor_hash)))
            .filter(DailyVisitor.day == today)
            .scalar()
            or 0
        ),
        "leads": _lead_panel(leads),
        "published": _published(),
        "recent_leads": [_lead_row(row) for row in recent_leads],
        "content": _content_status(),
        "top_pages": _top_pages(start),
        "seo": _seo_health(),
        "days": days,
    }


def _kpis():
    cards = [
        ("Total Pages", SitePage, {"status": "published"}, "Published pages", "pages"),
        ("Blog Articles", Article, {"status": "published"}, "Published insights", "articles"),
        ("Case Studies", CaseStudy, {"status": "published"}, "Published case studies", "studies"),
        ("Solutions", Offering, {"kind": "solution", "status": "published"}, "AI solution pages", "solutions"),
        ("Services", Offering, {"kind": "service", "status": "published"}, "Service pages", "services"),
        ("Industries", Offering, {"kind": "industry", "status": "published"}, "Industry pages", "industries"),
    ]
    rows = []
    for label, model, filters, hint, icon in cards:
        query = model.query.filter_by(**filters)
        rows.append({
            "label": label,
            "value": _comma(query.count()),
            "hint": hint,
            "icon": icon,
            "trend": _trend(model, **filters),
        })
    return rows


def _trend(model, **filters):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    prior = now - timedelta(days=60)
    column = model.created_at if hasattr(model, "created_at") else model.updated_at

    def between(begin, end):
        query = model.query.filter(column >= begin, column < end)
        for key, value in filters.items():
            query = query.filter(getattr(model, key) == value)
        return query.count()

    recent = between(start, now + timedelta(days=1))
    previous = between(prior, start)
    if recent == 0:
        return {"text": "No change", "tone": "flat"}
    if previous == 0:
        return {"text": f"+{recent} new", "tone": "up"}
    change = round((recent - previous) * 100 / previous)
    if change > 0:
        return {"text": f"↑ {change}%", "tone": "up"}
    if change < 0:
        return {"text": f"↓ {abs(change)}%", "tone": "down"}
    return {"text": "No change", "tone": "flat"}


def _daily_series(start, today):
    view_rows = (
        db.session.query(DailyPageView.day, func.sum(DailyPageView.views))
        .filter(DailyPageView.day >= start, DailyPageView.day <= today)
        .group_by(DailyPageView.day)
        .all()
    )
    visitor_rows = (
        db.session.query(DailyVisitor.day, func.count(func.distinct(DailyVisitor.visitor_hash)))
        .filter(DailyVisitor.day >= start, DailyVisitor.day <= today)
        .group_by(DailyVisitor.day)
        .all()
    )
    views = {_as_date(day): int(total or 0) for day, total in view_rows}
    visitors = {_as_date(day): int(total or 0) for day, total in visitor_rows}
    points = []
    day = start
    while day <= today:
        points.append({
            "label": f"{day.strftime('%b')} {day.day}",
            "views": views.get(day, 0),
            "visitors": visitors.get(day, 0),
        })
        day += timedelta(days=1)
    return points


def _view_total(start, end):
    total = (
        db.session.query(func.coalesce(func.sum(DailyPageView.views), 0))
        .filter(DailyPageView.day >= start, DailyPageView.day <= end)
        .scalar()
    )
    return int(total or 0)


def _chart(points):
    width, height = 640, 168
    left, right, top, bottom = 46, 8, 10, 8
    peak = max([point["views"] for point in points] + [point["visitors"] for point in points] + [4])

    def xy(index, value):
        x = left + (width - left - right) * (index / max(len(points) - 1, 1))
        y = top + (height - top - bottom) * (1 - (value / peak))
        return x, y

    def line(key):
        return " ".join(f"{xy(index, point[key])[0]:.1f},{xy(index, point[key])[1]:.1f}" for index, point in enumerate(points))

    coords = [xy(index, point["views"]) for index, point in enumerate(points)]
    area = ""
    if coords:
        area = (
            f"M{coords[0][0]:.1f},{height - bottom:.1f} "
            + " ".join(f"L{x:.1f},{y:.1f}" for x, y in coords)
            + f" L{coords[-1][0]:.1f},{height - bottom:.1f} Z"
        )
    ticks = []
    for step in range(5):
        value = int(round(peak * step / 4))
        y = top + (height - top - bottom) * (1 - (value / peak if peak else 0))
        ticks.append({"y": round(y, 1), "text": _comma(value)})
    labels = []
    for index, point in enumerate(points):
        if index % 5 == 0 or index == len(points) - 1:
            x, _y = xy(index, 0)
            labels.append({"x": round(x / width * 100, 2), "text": point["label"]})
    return {"views": line("views"), "visitors": line("visitors"), "area": area, "ticks": ticks, "labels": labels}


def _lead_panel(rows):
    colors = {
        "new": ("New", "#7B5DFF"),
        "contacted": ("Contacted", "#B35DFF"),
        "qualified": ("Qualified", "#22b8cf"),
        "opportunity": ("Opportunity", "#16a34a"),
        "won": ("Won", "#4ade80"),
        "proposal": ("Proposal", "#f59e0b"),
        "in progress": ("In progress", "#64748b"),
        "lost": ("Lost", "#ef4444"),
        "closed": ("Closed", "#94a3b8"),
    }
    counts = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    slices = []
    for key, (label, color) in colors.items():
        count = counts.get(key, 0)
        if count or key in {"new", "contacted", "qualified", "opportunity", "won"}:
            slices.append({"key": key, "label": label, "count": count, "color": color})
    return {"total": len(rows), "total_label": _comma(len(rows)), "style": _donut(slices), "slices": slices}


def _published():
    rows = []
    for article in Article.query.filter_by(status="published").all():
        rows.append(_pub("Blog", article.title, article.published_at or article.updated_at, "admin.article_edit", {"article_id": article.id}))
    for study in CaseStudy.query.filter_by(status="published").all():
        rows.append(_pub("Case Study", study.title, study.published_at or study.updated_at, "admin.study_edit", {"study_id": study.id}))
    endpoints = {"solution": "admin.solutions_edit", "service": "admin.services_edit", "industry": "admin.industries_edit"}
    kinds = {"solution": "Solution", "service": "Service", "industry": "Industry"}
    for item in Offering.query.filter_by(status="published").all():
        rows.append(_pub(kinds.get(item.kind, "Page"), item.name, item.published_at or item.updated_at, endpoints.get(item.kind, "admin.solutions_edit"), {"item_id": item.id}))
    rows.sort(key=lambda row: row["sort"] or "", reverse=True)
    return rows[:5]


def _pub(kind, title, when, endpoint, params):
    return {
        "kind": kind,
        "title": title,
        "when": _date_label(when),
        "sort": when.isoformat() if when else "",
        "url": url_for(endpoint, **params),
        "initials": _initials(title),
    }


def _lead_row(row):
    source = (row.utm_source or row.source_page or "Contact form").strip() or "Contact form"
    return {
        "name": row.name,
        "company": row.company or "—",
        "source": source[:42],
        "when": _date_label(row.created_at),
        "url": url_for("admin.inquiry", inquiry_id=row.id),
        "initials": _initials(row.name),
        "color": _palette(row.id or 0),
    }


def _content_status():
    buckets = {"published": 0, "draft": 0, "review": 0, "scheduled": 0}
    for model in (Article, CaseStudy, Offering, SitePage):
        for status, count in db.session.query(model.status, func.count()).group_by(model.status).all():
            if status in buckets:
                buckets[status] += int(count)
    slices = [
        {"label": "Published", "count": buckets["published"], "color": "#22c55e"},
        {"label": "Draft", "count": buckets["draft"], "color": "#eab308"},
        {"label": "In Review", "count": buckets["review"], "color": "#7B5DFF"},
        {"label": "Scheduled", "count": buckets["scheduled"], "color": "#8b5cf6"},
    ]
    total = sum(item["count"] for item in slices)
    return {"total": total, "total_label": _comma(total), "style": _donut(slices), "slices": slices}


def _top_pages(start):
    rows = (
        db.session.query(DailyPageView.path, func.sum(DailyPageView.views))
        .filter(DailyPageView.day >= start)
        .group_by(DailyPageView.path)
        .order_by(func.sum(DailyPageView.views).desc())
        .limit(5)
        .all()
    )
    clicks = dict(
        db.session.query(ConversionEvent.path, func.count())
        .filter(ConversionEvent.name.in_(("cta_click", "contact_click", "contact_submit")))
        .group_by(ConversionEvent.path)
        .all()
    )
    leads = dict(
        db.session.query(ContactSubmission.source_page, func.count())
        .filter(ContactSubmission.archived.is_(False), ContactSubmission.source_page != "")
        .group_by(ContactSubmission.source_page)
        .all()
    )
    return [
        {"path": path, "views": _comma(int(views or 0)), "clicks": _comma(int(clicks.get(path, 0))), "leads": _comma(int(leads.get(path, 0)))}
        for path, views in rows
    ]


def _seo_health():
    grades = {"Good": 0, "Needs improvement": 0, "Critical": 0}
    for page in SitePage.query.all():
        grade, _checks = seo_checks(page.seo_title or page.hero_title or page.title, page.meta_description or page.summary, page.hero_title or page.title, bool(page.hero_image))
        grades[grade] = grades.get(grade, 0) + 1
    for article in Article.query.all():
        grade, _checks = seo_checks(article.seo_title or article.title, article.meta_description or article.excerpt, article.title, bool(article.featured_image), True, bool(article.canonical_url) or True)
        grades[grade] = grades.get(grade, 0) + 1
    for item in Offering.query.all():
        grade, _checks = seo_checks(item.seo_title or item.name, item.meta_description or item.summary, item.name, bool(item.hero_image or item.icon))
        grades[grade] = grades.get(grade, 0) + 1
    total = sum(grades.values())
    score = round(100 * grades["Good"] / total) if total else 0
    slices = [
        {"label": "Good", "count": grades["Good"], "color": "#22c55e"},
        {"label": "Needs improvement", "count": grades["Needs improvement"], "color": "#eab308"},
        {"label": "Critical", "count": grades["Critical"], "color": "#ef4444"},
    ]
    return {"score": score, "style": _score_ring(score), "slices": slices}


def _donut(slices):
    total = sum(item["count"] for item in slices)
    if total <= 0:
        return "conic-gradient(#e8edf5 0deg 360deg)"
    cursor = 0
    parts = []
    for item in slices:
        if item["count"] <= 0:
            continue
        start = cursor / total * 360
        cursor += item["count"]
        end = cursor / total * 360
        parts.append(f"{item['color']} {start:.2f}deg {end:.2f}deg")
    return "conic-gradient(" + ", ".join(parts) + ")"


def _score_ring(score):
    degrees = max(0, min(100, score)) * 3.6
    return f"conic-gradient(#22c55e 0deg {degrees:.2f}deg, #e8edf5 {degrees:.2f}deg 360deg)"


def _pct(current, previous):
    if previous <= 0:
        return None
    return round((current - previous) * 100 / previous)


def _comma(value):
    return f"{int(value):,}"


def _as_date(value):
    if hasattr(value, "hour"):
        return value.date()
    if hasattr(value, "year"):
        return value
    text = str(value)[:10]
    year, month, day = text.split("-")
    from datetime import date
    return date(int(year), int(month), int(day))


def _date_label(value):
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return f"{value.strftime('%b')} {value.day}, {value.year}"
    return str(value)[:10]


def _initials(text):
    parts = [part for part in (text or "").replace("-", " ").split() if part]
    if not parts:
        return "NX"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _palette(seed):
    colors = ["#EDE7FF", "#F3EEFF", "#F4FFC8", "#E9F5ED", "#F5F5F5"]
    return colors[seed % len(colors)]
