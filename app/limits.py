"""Database-backed request limits shared by every application worker."""

from datetime import datetime, timezone

from flask import current_app, request

from app.extensions import db
from app.models import RequestRate


def rate_limited(scope, limit, seconds):
    address = (request.remote_addr or "unknown")[:64]
    bucket = f"{scope}:{address}"[:180]
    now = datetime.now(timezone.utc)
    try:
        row = db.session.get(RequestRate, bucket)
        if row is None:
            db.session.add(RequestRate(bucket=bucket, window_start=now, hits=1))
            db.session.commit()
            return False
        started = row.window_start
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started is None or (now - started).total_seconds() >= seconds:
            row.window_start = now
            row.hits = 1
            db.session.commit()
            return False
        if row.hits >= limit:
            return True
        row.hits += 1
        db.session.commit()
        return False
    except Exception:
        db.session.rollback()
        current_app.logger.warning("Shared rate limit for %s could not be stored", scope, exc_info=True)
        return False
