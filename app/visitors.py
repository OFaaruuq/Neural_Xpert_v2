import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import DailyPageView, DailyVisitor

_BOT_MARKERS = ("bot", "spider", "crawler", "slurp", "preview", "wget", "curl", "headless")


def _today():
    return datetime.now(timezone.utc).date()


def record_public_visit(response):
    if request.method != "GET" or response.status_code != 200:
        return response
    content_type = response.content_type or ""
    if "html" not in content_type:
        return response
    path = request.path or "/"
    if path.startswith(("/admin", "/static")) or path in {"/robots.txt", "/sitemap.xml"}:
        return response
    agent = (request.headers.get("User-Agent") or "").lower()
    if any(marker in agent for marker in _BOT_MARKERS):
        return response
    token = request.cookies.get("nx_visitor") or ""
    fresh = len(token) < 20
    if fresh:
        token = secrets.token_urlsafe(24)
    try:
        _store_visit(path[:300], token)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Visitor count was not stored")
        return response
    if fresh:
        response.set_cookie(
            "nx_visitor",
            token,
            max_age=60 * 60 * 24 * 400,
            httponly=True,
            samesite="Lax",
            secure=bool(current_app.config.get("SESSION_COOKIE_SECURE")),
            path="/",
        )
    return response


def _store_visit(path, token):
    day = _today()
    digest = hashlib.sha256(f"{current_app.config['SECRET_KEY']}:{token}".encode()).hexdigest()
    view = DailyPageView.query.filter_by(day=day, path=path).first()
    if view is None:
        view = DailyPageView(day=day, path=path, views=1)
        db.session.add(view)
    else:
        view.views += 1
    if DailyVisitor.query.filter_by(day=day, visitor_hash=digest).first() is None:
        db.session.add(DailyVisitor(day=day, visitor_hash=digest))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def traffic_summary():
    today = _today()
    windows = {"today": today, "week": today - timedelta(days=6), "month": today - timedelta(days=29)}
    summary = {}
    for name, start in windows.items():
        summary[f"{name}_views"] = (
            db.session.query(db.func.coalesce(db.func.sum(DailyPageView.views), 0))
            .filter(DailyPageView.day >= start)
            .scalar()
        )
        summary[f"{name}_visitors"] = (
            db.session.query(db.func.count(db.func.distinct(DailyVisitor.visitor_hash)))
            .filter(DailyVisitor.day >= start)
            .scalar()
        )
    summary["top_pages"] = (
        db.session.query(DailyPageView.path, db.func.sum(DailyPageView.views))
        .filter(DailyPageView.day >= windows["week"])
        .group_by(DailyPageView.path)
        .order_by(db.func.sum(DailyPageView.views).desc())
        .limit(8)
        .all()
    )
    return summary
