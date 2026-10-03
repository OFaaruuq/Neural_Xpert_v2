import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import DailyPageView, DailyVisitor, PageVisit

_BOT_MARKERS = ("bot", "spider", "crawler", "slurp", "preview", "wget", "curl", "headless")
_IP_CHARS = re.compile(r"^[0-9A-Fa-f:.]+$")
_PER_PAGE = 20


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


def client_ip():
    address = (request.remote_addr or "").strip()
    if not _IP_CHARS.fullmatch(address or ""):
        return ""
    return address[:64]


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
    agent = (request.headers.get("User-Agent") or "").strip()
    db.session.add(PageVisit(
        ip_address=client_ip(),
        path=path,
        user_agent=agent[:300],
        visitor_hash=digest,
    ))
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


def _like(term):
    cleaned = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{cleaned}%"


def _page_count(total, per_page):
    return max(1, (total + per_page - 1) // per_page)


def visitor_report(search="", address="", page=1, log_page=1, per_page=_PER_PAGE):
    """Live unique-IP list plus the visit log behind the current filter."""
    search = (search or "").strip()[:80]
    address = (address or "").strip()[:64]
    if address and not _IP_CHARS.fullmatch(address):
        address = ""
    page = max(1, int(page or 1))
    log_page = max(1, int(log_page or 1))
    today = _today()
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    grouped = db.session.query(
        PageVisit.ip_address,
        db.func.count(PageVisit.id),
        db.func.min(PageVisit.visited_at),
        db.func.max(PageVisit.visited_at),
        db.func.max(PageVisit.id),
    )
    address_count = db.session.query(db.func.count(db.func.distinct(PageVisit.ip_address)))
    hits = PageVisit.query
    if address:
        grouped = grouped.filter(PageVisit.ip_address == address)
        address_count = address_count.filter(PageVisit.ip_address == address)
        hits = hits.filter(PageVisit.ip_address == address)
    elif search:
        like = _like(search)
        ip_match = PageVisit.ip_address.ilike(like, escape="\\")
        path_match = PageVisit.path.ilike(like, escape="\\")
        matched = db.session.query(PageVisit.ip_address).filter(db.or_(ip_match, path_match)).distinct()
        grouped = grouped.filter(PageVisit.ip_address.in_(matched))
        address_count = address_count.filter(PageVisit.ip_address.in_(matched))
        hits = hits.filter(db.or_(ip_match, path_match))
    grouped = grouped.group_by(PageVisit.ip_address).order_by(db.func.max(PageVisit.visited_at).desc())
    address_total = address_count.scalar() or 0
    address_pages = _page_count(address_total, per_page)
    page = min(page, address_pages)
    address_rows = grouped.offset((page - 1) * per_page).limit(per_page).all()
    last_ids = [row[4] for row in address_rows if row[4]]
    last_visits = {}
    if last_ids:
        last_visits = {row.id: row for row in PageVisit.query.filter(PageVisit.id.in_(last_ids))}
    addresses = []
    for ip_address, visits, first_seen, last_seen, last_id in address_rows:
        last = last_visits.get(last_id)
        addresses.append({
            "ip_address": ip_address or "Unknown",
            "visits": visits,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "last_path": last.path if last else "",
            "user_agent": last.user_agent if last else "",
        })

    hit_total = hits.count()
    log_pages = _page_count(hit_total, per_page)
    log_page = min(log_page, log_pages)
    log_rows = (
        hits.order_by(PageVisit.visited_at.desc(), PageVisit.id.desc())
        .offset((log_page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "search": search,
        "selected": address,
        "unique_total": db.session.query(db.func.count(db.func.distinct(PageVisit.ip_address))).scalar() or 0,
        "addresses": addresses,
        "address_total": address_total,
        "address_page": page,
        "address_pages": address_pages,
        "hits": log_rows,
        "hit_total": hit_total,
        "log_page": log_page,
        "log_pages": log_pages,
        "today_hits": PageVisit.query.filter(PageVisit.visited_at >= day_start, PageVisit.visited_at < day_end).count(),
        "today_ips": (
            db.session.query(db.func.count(db.func.distinct(PageVisit.ip_address)))
            .filter(PageVisit.visited_at >= day_start, PageVisit.visited_at < day_end)
            .scalar()
        ) or 0,
        "latest": PageVisit.query.order_by(PageVisit.visited_at.desc(), PageVisit.id.desc()).first(),
    }


def visitor_export_rows(search="", address="", limit=20000):
    report_search = (search or "").strip()[:80]
    report_address = (address or "").strip()[:64]
    if report_address and not _IP_CHARS.fullmatch(report_address):
        report_address = ""
    query = PageVisit.query
    if report_address:
        query = query.filter(PageVisit.ip_address == report_address)
    elif report_search:
        like = _like(report_search)
        query = query.filter(db.or_(
            PageVisit.ip_address.ilike(like, escape="\\"),
            PageVisit.path.ilike(like, escape="\\"),
        ))
    return query.order_by(PageVisit.visited_at.desc(), PageVisit.id.desc()).limit(limit).all()
