import re
import time
from io import BytesIO

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
        from app.models import DailyPageView, DailyVisitor, PageVisit

        views = DailyPageView.query.filter_by(path="/").one().views
        visitors = DailyVisitor.query.count()
        visits = PageVisit.query.filter_by(path="/").count()
    assert views == 2
    assert visitors == 1
    assert visits == 2


def test_admin_lists_every_visitor_ip(client, app):
    client.get("/", environ_base={"REMOTE_ADDR": "203.0.113.10"})
    client.get("/about", environ_base={"REMOTE_ADDR": "203.0.113.10"})
    client.get("/", environ_base={"REMOTE_ADDR": "198.51.100.4"})
    with app.app_context():
        _staff, password = create_staff("traffic@neuralxpert.com")
    home = _open_dashboard(client, app, "traffic@neuralxpert.com", password)
    assert b"Visitor IPs" in home.data
    page = client.get("/admin/visitors")
    assert page.status_code == 200
    assert b"203.0.113.10" in page.data
    assert b"198.51.100.4" in page.data
    assert b"/about" in page.data
    narrowed = client.get("/admin/visitors?ip=203.0.113.10")
    assert b"203.0.113.10" in narrowed.data
    assert b"/about" in narrowed.data
    assert b"198.51.100.4" not in narrowed.data
    found = client.get("/admin/visitors?q=/about")
    assert b"203.0.113.10" in found.data
    assert b"198.51.100.4" not in found.data
    exported = client.get("/admin/visitors.csv")
    assert exported.status_code == 200
    assert b"203.0.113.10" in exported.data
    assert b"198.51.100.4" in exported.data
    analytics = client.get("/admin/analytics")
    assert b"Unique IP addresses" in analytics.data


_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_admin_uploads_images_with_size_and_radius(client, app):
    with app.app_context():
        _staff, password = create_staff("images@neuralxpert.com")
    _open_dashboard(client, app, "images@neuralxpert.com", password)
    pages = client.get("/admin/pages")
    assert pages.status_code == 200
    page_id = re.search(br"/admin/pages/(\d+)", pages.data).group(1)
    editor = client.get(f"/admin/pages/{page_id.decode()}")
    assert b"Radius (px)" in editor.data
    assert b'name="hero_image_file"' in editor.data
    insight = client.post(
        "/admin/insights/new",
        data={
            "title": "Image briefing",
            "excerpt": "Shows the uploaded picture",
            "content": "<p>Body</p>",
            "status": "published",
            "image_width": "320",
            "image_height": "180",
            "image_radius": "18",
            "featured_image_file": (BytesIO(_PNG), "brief.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Insight saved." in insight.data
    assert b"border-radius:18px" in insight.data
    with app.app_context():
        from app.models import Article

        article = Article.query.filter_by(title="Image briefing").one()
        assert article.featured_image.startswith("uploads/")
        assert article.image_width == 320
        assert article.image_height == 180
        assert article.image_radius == 18
        slug = article.slug
    public = client.get(f"/insights/{slug}")
    assert public.status_code == 200
    assert b"border-radius:18px" in public.data
    assert b"width:320px" in public.data
    solution = client.post(
        "/admin/solutions/new",
        data={
            "name": "Secure copilots",
            "summary": "A published solution",
            "status": "published",
            "image_width": "280",
            "image_height": "160",
            "image_radius": "22",
            "hero_image_file": (BytesIO(_PNG), "copilot.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Solution saved." in solution.data
    with app.app_context():
        from app.models.platform import Offering

        item = Offering.query.filter_by(name="Secure copilots").one()
        assert item.hero_image.startswith("uploads/")
        assert item.image_radius == 22
        slug = item.slug
    detail = client.get(f"/solutions/{slug}")
    assert b"border-radius:22px" in detail.data
    assert b"width:280px" in detail.data
