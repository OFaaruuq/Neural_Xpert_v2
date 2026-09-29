import re
import time

import pyotp

from app.admin.security import create_staff
from app.extensions import mail
from app.models import Article, ContactSubmission, StaffUser


def _sign_in(client, app, email, password):
    app.config["MAIL_SERVER"] = "smtp.example.com"
    app.config["MAIL_SUPPRESS_SEND"] = True
    app.config["ADMIN_OTP_ON_PAGE"] = False
    app.config["MAIL_DEFAULT_SENDER"] = "Neural Xpert"
    app.config["MAIL_USERNAME"] = "neuralxperts@gmail.com"
    with app.app_context():
        with mail.record_messages() as outbox:
            response = client.post("/admin/login", data={"email": email, "password": password})
            code = re.search(r"\b(\d{6})\b", outbox[0].body).group(1)
    assert response.status_code == 302
    return code


def test_staff_must_use_password_email_code_and_authenticator(client, app):
    with app.app_context():
        _staff, password = create_staff("ops@neuralxpert.com")
    code = _sign_in(client, app, "ops@neuralxpert.com", password)
    assert client.get("/admin/").headers["Location"].endswith("/admin/login")
    page = client.get("/admin/verify")
    assert code.encode() not in page.data
    setup = client.post("/admin/verify", data={"email_code": code}, follow_redirects=True)
    assert b"Set up Google Authenticator" in setup.data
    with app.app_context():
        staff = StaffUser.query.filter_by(email="ops@neuralxpert.com").first()
        totp = pyotp.TOTP(staff.totp_secret)
        current = totp.now()
    enrolled = client.post("/admin/enroll", data={"totp_code": current}, follow_redirects=True)
    assert b"Save your recovery codes" in enrolled.data
    home = client.post("/admin/recovery", follow_redirects=True)
    assert b"Visitors today" in home.data
    assert b"Open CRM" in home.data
    assert b"Users" in home.data
    assert b"Roles and permissions" in home.data
    account = client.get("/admin/account")
    assert b"Change password" in account.data
    assert b"Current password" in account.data
    client.post("/admin/logout")
    code = _sign_in(client, app, "ops@neuralxpert.com", password)
    rejected = client.post("/admin/verify", data={"email_code": code, "totp_code": "000000"})
    assert b"not valid" in rejected.data
    with app.app_context():
        staff = StaffUser.query.filter_by(email="ops@neuralxpert.com").first()
        nxt = pyotp.TOTP(staff.totp_secret).generate_otp(int(time.time() // 30) + 1)
    accepted = client.post("/admin/verify", data={"email_code": code, "totp_code": nxt}, follow_redirects=True)
    assert b"Visitors today" in accepted.data


def test_admin_can_update_an_inquiry_and_keep_an_edited_article(client, app):
    with app.app_context():
        _staff, password = create_staff("editor@neuralxpert.com")
        db_article = Article.query.filter_by(slug="rathat-android-trojan-uses-ai-for-automation").first()
        article_id = db_article.id
        inquiry = ContactSubmission(name="Ada", email="ada@example.com", phone="1", subject="AI", message="Hello")
        from app.extensions import db

        db.session.add(inquiry)
        db.session.commit()
        inquiry_id = inquiry.id
    code = _sign_in(client, app, "editor@neuralxpert.com", password)
    client.post("/admin/verify", data={"email_code": code})
    with app.app_context():
        staff = StaffUser.query.filter_by(email="editor@neuralxpert.com").first()
        totp = pyotp.TOTP(staff.totp_secret).now()
    client.post("/admin/enroll", data={"totp_code": totp})
    client.post("/admin/recovery")
    saved = client.post(f"/admin/inquiries/{inquiry_id}", data={"status": "in progress", "notes": "Called back"}, follow_redirects=True)
    assert b"Inquiry updated." in saved.data
    edited = client.post(
        f"/admin/insights/{article_id}",
        data={"title": "RatHat briefing", "excerpt": "Updated in admin", "content": "<p>Updated body</p>", "status": "published"},
        follow_redirects=True,
    )
    assert b"Insight saved." in edited.data
    with app.app_context():
        from app.seed import seed

        seed()
        from app.extensions import db

        article = db.session.get(Article, article_id)
        assert article.managed_in_admin is True
        assert article.excerpt == "Updated in admin"


def _open_dashboard(client, app, email, password):
    code = _sign_in(client, app, email, password)
    client.post("/admin/verify", data={"email_code": code})
    with app.app_context():
        staff = StaffUser.query.filter_by(email=email).first()
        totp = pyotp.TOTP(staff.totp_secret).now()
    client.post("/admin/enroll", data={"totp_code": totp})
    return client.post("/admin/recovery", follow_redirects=True)


def test_viewer_cannot_manage_users(client, app):
    with app.app_context():
        from app.extensions import db
        from app.models import StaffRole

        staff, password = create_staff("viewer@neuralxpert.com")
        staff.role = StaffRole.query.filter_by(slug="viewer").one()
        db.session.commit()
    home = _open_dashboard(client, app, "viewer@neuralxpert.com", password)
    assert b"Visitors today" in home.data
    assert b"Roles and permissions" not in home.data
    denied = client.get("/admin/users")
    assert denied.status_code == 403
    assert b"Access denied" in denied.data
    crm = client.get("/admin/crm")
    assert b"CRM" in crm.data


def test_public_visit_is_counted(client, app):
    client.get("/")
    client.get("/")
    with app.app_context():
        from app.models import DailyPageView, DailyVisitor

        views = DailyPageView.query.filter_by(path="/").one().views
        visitors = DailyVisitor.query.count()
    assert views == 2
    assert visitors == 1
