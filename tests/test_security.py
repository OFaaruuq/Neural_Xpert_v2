from app.extensions import db
from app.models.platform import RedirectRule, SiteSetting
from app.services import safe_local_path, safe_url, sanitize_html


def test_public_html_drops_active_content(app):
    with app.app_context():
        cleaned = sanitize_html(
            '<p>Hi</p><script>alert(1)</script><img src="x" onerror="alert(1)">'
            '<svg/onload=alert(1)></svg><a href="javascript:alert(1)">x</a>'
            '<h3 class="h4">Title</h3><a href="https://neuralxpert.com">site</a>'
        )
    lowered = cleaned.lower()
    assert "<script" not in lowered
    assert "onerror" not in lowered
    assert "onload" not in lowered
    assert "javascript:" not in lowered
    assert "Title" in cleaned
    assert "https://neuralxpert.com" in cleaned
    assert safe_url("//evil.example") == ""
    assert safe_url("javascript:alert(1)") == ""
    assert safe_local_path("/careers") == "/careers"
    assert safe_local_path("https://evil.example") == ""


def test_security_headers_are_set(client):
    response = client.get("/")
    policy = response.headers["Content-Security-Policy"]
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'self'" in policy
    assert "script-src 'self' 'nonce-" in policy
    assert "script-src 'self' 'unsafe-inline'" not in policy
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    html = response.get_data(as_text=True)
    nonce = policy.split("'nonce-", 1)[1].split("'", 1)[0]
    assert f'nonce="{nonce}"' in html


def test_redirects_cannot_leave_the_site(client, app):
    with app.app_context():
        db.session.add(RedirectRule(source="/gone-external", target="https://evil.example/phish", enabled=True, status_code=301))
        db.session.add(RedirectRule(source="/gone-local", target="/careers", enabled=True, status_code=301))
        db.session.commit()
    external = client.get("/gone-external")
    assert "evil.example" not in external.headers.get("Location", "")
    local = client.get("/gone-local")
    assert local.status_code == 301
    assert local.headers["Location"].endswith("/careers")


def test_media_files_require_a_staff_session(client):
    response = client.get("/admin/files/1/not-a-real-file.png")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/login")
    assert response.headers["Cache-Control"] == "no-store"


def test_login_limit_is_shared_across_workers(client):
    for _ in range(8):
        response = client.post("/admin/login", data={"email": "nobody@neuralxpert.com", "password": "wrong-password"})
        assert response.status_code == 200
    blocked = client.post("/admin/login", data={"email": "nobody@neuralxpert.com", "password": "wrong-password"})
    assert blocked.status_code == 429


def test_authenticator_secret_is_sealed(app):
    from sqlalchemy import text

    from app.admin.security import begin_enrollment, create_staff
    from app.models import StaffUser

    with app.app_context():
        staff, _password = create_staff("otp@neuralxpert.com")
        with app.test_request_context():
            begin_enrollment(staff)
        raw = db.session.execute(text("SELECT totp_secret FROM staff_users WHERE id = :id"), {"id": staff.id}).scalar()
        assert str(raw).startswith("nx1:")
        loaded = db.session.get(StaffUser, staff.id)
        assert not loaded.totp_secret.startswith("nx1:")
        assert len(loaded.totp_secret) >= 16


def test_smtp_password_is_sealed_at_rest(app):
    from app.admin.catalog import ensure_catalog
    from app.mailer import apply_mail_settings, save_mail_settings

    with app.app_context():
        ensure_catalog()
        error = save_mail_settings(
            {
                "mail_server": "smtp.example.com",
                "mail_port": "587",
                "mail_username": "ops@neuralxpert.com",
                "mail_recipient": "inbox@neuralxpert.com",
                "mail_password": "s3cret-value",
            }
        )
        assert error == ""
        db.session.commit()
        stored = SiteSetting.query.filter_by(key="mail_password").one().value
        assert stored.startswith("nx1:")
        assert "s3cret-value" not in stored
        apply_mail_settings()
        assert app.config["MAIL_PASSWORD"] == "s3cret-value"
