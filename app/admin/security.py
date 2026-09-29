import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

import pyotp
from email_validator import EmailNotValidError, validate_email
from flask import current_app, session
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.mailer import send_email
from app.models import LoginChallenge, StaffUser

LOGIN_ERROR = "Email or password is incorrect."
CODE_ERROR = "That code is not valid or has expired."
LOCK_MINUTES = 15
OTP_MINUTES = 10
MAX_ATTEMPTS = 5


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def normalize_email(value):
    try:
        return validate_email((value or "").strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return ""


def create_staff(email):
    normalized = normalize_email(email)
    if not normalized:
        raise ValueError("Enter a valid staff email address.")
    if StaffUser.query.filter_by(email=normalized).first():
        raise ValueError("That staff account already exists.")
    from app.admin.access import ensure_roles
    from app.models import StaffRole

    ensure_roles()
    password = secrets.token_urlsafe(18)
    staff = StaffUser(
        email=normalized,
        password_hash=generate_password_hash(password),
        is_active=True,
        role=StaffRole.query.filter_by(slug="administrator").one(),
    )
    db.session.add(staff)
    db.session.commit()
    return staff, password


def _dummy_hash():
    return generate_password_hash("not-a-real-staff-password")


def account_is_locked(staff):
    locked_until = as_utc(staff.locked_until)
    return bool(locked_until and locked_until > utcnow())


def register_failure(staff):
    if staff is None:
        return
    staff.failed_attempts += 1
    if staff.failed_attempts >= MAX_ATTEMPTS:
        staff.failed_attempts = 0
        staff.locked_until = utcnow() + timedelta(minutes=LOCK_MINUTES)
    db.session.commit()


def check_password(staff, password):
    hashed = staff.password_hash if staff else _dummy_hash()
    return check_password_hash(hashed, password or "")


def _otp_hash(staff_id, code):
    secret = current_app.config["SECRET_KEY"]
    payload = f"{secret}:{staff_id}:{code}".encode()
    return hashlib.sha256(payload).hexdigest()


def start_email_otp(staff):
    LoginChallenge.query.filter_by(staff_id=staff.id, used=False).update({"used": True})
    code = f"{secrets.randbelow(1000000):06d}"
    challenge = LoginChallenge(
        staff_id=staff.id,
        code_hash=_otp_hash(staff.id, code),
        expires_at=utcnow() + timedelta(minutes=OTP_MINUTES),
    )
    db.session.add(challenge)
    db.session.commit()
    sent = send_email(
        subject="Your Neural Xpert sign-in code",
        recipients=[staff.email],
        body=(
            "Your Neural Xpert admin sign-in code is "
            f"{code}. It expires in {OTP_MINUTES} minutes.\n\n"
            "After this code, sign-in asks for Google Authenticator.\n\n"
            "If you did not try to sign in, ignore this email.\n"
        ),
    )
    if not sent and not current_app.config.get("ADMIN_OTP_ON_PAGE"):
        challenge.used = True
        db.session.commit()
        return None
    session.clear()
    session["login_staff_id"] = staff.id
    session["login_challenge_id"] = challenge.id
    session.permanent = True
    if not sent and current_app.config.get("ADMIN_OTP_ON_PAGE"):
        session["login_dev_code"] = code
    return challenge


def pending_login():
    staff_id = session.get("login_staff_id")
    challenge_id = session.get("login_challenge_id")
    if not staff_id or not challenge_id:
        return None, None
    staff = db.session.get(StaffUser, staff_id)
    challenge = db.session.get(LoginChallenge, challenge_id)
    if staff is None or challenge is None or challenge.staff_id != staff.id:
        return None, None
    return staff, challenge


def _challenge_is_open(challenge):
    if challenge.used or challenge.attempts >= MAX_ATTEMPTS:
        return False
    expires = as_utc(challenge.expires_at)
    return bool(expires and expires > utcnow())


def check_email_code(staff, challenge, code):
    if not _challenge_is_open(challenge):
        return False
    supplied = "".join(ch for ch in (code or "") if ch.isdigit())
    if secrets.compare_digest(challenge.code_hash, _otp_hash(staff.id, supplied)):
        return True
    challenge.attempts += 1
    if challenge.attempts >= MAX_ATTEMPTS:
        challenge.used = True
    db.session.commit()
    return False


def verify_totp(staff, code):
    if not staff.totp_secret:
        return False
    supplied = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(supplied) != 6:
        return False
    totp = pyotp.TOTP(staff.totp_secret)
    now_step = int(time.time() // 30)
    matched = None
    for offset in (-1, 0, 1):
        candidate = now_step + offset
        if secrets.compare_digest(totp.generate_otp(candidate), supplied):
            matched = candidate
            break
    if matched is None or matched <= (staff.last_totp_step or 0):
        return False
    staff.last_totp_step = matched
    db.session.commit()
    return True


def consume_recovery_code(staff, code):
    supplied = (code or "").strip().lower().replace(" ", "")
    if not supplied:
        return False
    kept = []
    matched = False
    for hashed in filter(None, (staff.recovery_hashes or "").splitlines()):
        if not matched and check_password_hash(hashed, supplied):
            matched = True
            continue
        kept.append(hashed)
    if matched:
        staff.recovery_hashes = "\n".join(kept)
        db.session.commit()
    return matched


def begin_enrollment(staff):
    if not staff.totp_secret or staff.totp_enabled:
        staff.totp_secret = pyotp.random_base32()
        staff.totp_enabled = False
        db.session.commit()
    session.clear()
    session["enroll_staff_id"] = staff.id
    session.permanent = True


def provisioning_uri(staff):
    return pyotp.TOTP(staff.totp_secret).provisioning_uri(name=staff.email, issuer_name="Neural Xpert")


def confirm_enrollment(staff, code):
    if not verify_totp(staff, code):
        return None
    codes = [secrets.token_hex(4) for _ in range(8)]
    staff.recovery_hashes = "\n".join(generate_password_hash(item) for item in codes)
    staff.totp_enabled = True
    staff.failed_attempts = 0
    staff.locked_until = None
    db.session.commit()
    session["recovery_codes"] = codes
    return codes


def complete_login(staff):
    staff.failed_attempts = 0
    staff.locked_until = None
    db.session.commit()
    session.clear()
    session["staff_id"] = staff.id
    session["mfa_complete"] = True
    session["staff_seen"] = int(time.time())
    session.permanent = True


def session_is_fresh():
    seen = session.get("staff_seen")
    now = int(time.time())
    if seen and now - int(seen) > 2 * 60 * 60:
        session.clear()
        return False
    session["staff_seen"] = now
    return True


def current_staff():
    if not session.get("mfa_complete"):
        return None
    staff = db.session.get(StaffUser, session.get("staff_id"))
    if staff is None or not staff.is_active or not staff.totp_enabled:
        return None
    return staff
