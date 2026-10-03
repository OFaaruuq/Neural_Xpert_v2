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


def test_admin_can_manage_records_redirects_and_media(client, app):
    with app.app_context():
        _staff, password = create_staff("records@neuralxpert.com")
    home = _open_dashboard(client, app, "records@neuralxpert.com", password)
    assert b"Credentials" in home.data
    assert b'href="/admin/credentials"' in home.data
    for path in (
        "/admin/",
        "/admin/pages",
        "/admin/homepage",
        "/admin/solutions",
        "/admin/services",
        "/admin/industries",
        "/admin/case-studies",
        "/admin/case-studies/new",
        "/admin/insights/new",
        "/admin/solutions/new",
        "/admin/crm/new",
        "/admin/careers/new",
        "/admin/insights",
        "/admin/media",
        "/admin/crm",
        "/admin/careers",
        "/admin/applications",
        "/admin/seo",
        "/admin/analytics",
        "/admin/visitors",
        "/admin/conversions",
        "/admin/partners",
        "/admin/credentials",
        "/admin/testimonials",
        "/admin/navigation",
        "/admin/email",
        "/admin/ask-ai",
        "/admin/settings",
        "/admin/redirects",
        "/admin/backups",
        "/admin/revisions",
        "/admin/workflow",
        "/admin/users",
        "/admin/access-roles",
        "/admin/audit-logs",
        "/admin/health",
        "/admin/account",
    ):
        page = client.get(path)
        assert page.status_code == 200, path

    blank = client.post("/admin/partners", data={"name": " "}, follow_redirects=True)
    assert b"Organization is required." in blank.data
    saved = client.post(
        "/admin/partners",
        data={"name": "Acme Cloud", "relationship": "Technology", "evidence": "Contract on file"},
        follow_redirects=True,
    )
    assert b"Partners saved." in saved.data
    assert b"Acme Cloud" in saved.data
    with app.app_context():
        from app.models.platform import Partner

        partner_id = Partner.query.filter_by(name="Acme Cloud").one().id
    updated = client.post(
        "/admin/partners",
        data={"row_id": partner_id, "name": "Acme Systems", "relationship": "Technology", "evidence": "Contract on file"},
        follow_redirects=True,
    )
    assert b"Acme Systems" in updated.data
    removed = client.post("/admin/partners", data={"delete_id": partner_id}, follow_redirects=True)
    assert b"Partners removed." in removed.data
    assert b"Acme Systems" not in removed.data

    credential = client.post(
        "/admin/credentials",
        data={"name": "ISO 27001", "issuer": "BSI", "issued_on": "2026-01-15"},
        follow_redirects=True,
    )
    assert b"ISO 27001" in credential.data
    blocked = client.post(
        "/admin/testimonials",
        data={"customer": "Amina", "quote": "Clear delivery", "status": "published"},
    )
    assert b"Customer approval is required" in blocked.data

    added = client.post("/admin/redirects", data={"source": "/old-offer", "target": "/solutions"}, follow_redirects=True)
    assert b"/old-offer" in added.data
    with app.app_context():
        from app.models.platform import RedirectRule

        rule_id = RedirectRule.query.filter_by(source="/old-offer").one().id
    disabled = client.post("/admin/redirects", data={"toggle_id": rule_id}, follow_redirects=True)
    assert b"Off" in disabled.data
    gone = client.post("/admin/redirects", data={"delete_id": rule_id}, follow_redirects=True)
    assert b"Redirect removed." in gone.data
    assert b"/old-offer" not in gone.data

    menu = client.post(
        "/admin/navigation",
        data={"create": "1", "menu": "footer", "label": "Careers link", "url": "/careers"},
        follow_redirects=True,
    )
    assert b"Careers link" in menu.data
    with app.app_context():
        from app.models.platform import NavItem

        item_id = NavItem.query.filter_by(label="Careers link").one().id
    client.post("/admin/navigation", data={"delete_id": item_id}, follow_redirects=True)
    with app.app_context():
        from app.models.platform import NavItem

        assert NavItem.query.filter_by(label="Careers link").first() is None

    homepage = client.get("/admin/homepage?focus=cta")
    assert b'id="cta"' in homepage.data

    uploaded = client.post(
        "/admin/media",
        data={"alt_text": "Office lobby", "folder": "general", "file": (BytesIO(_PNG), "lobby.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Office lobby" in uploaded.data
    with app.app_context():
        from app.models.platform import MediaAsset

        asset = MediaAsset.query.filter_by(alt_text="Office lobby").one()
        asset_id = asset.id
        filename = asset.filename
    opened = client.get(f"/admin/files/{asset_id}/{filename}")
    assert opened.status_code == 200
    assert opened.data.startswith(b"\x89PNG")
    client.post("/admin/media", data={"delete_id": asset_id}, follow_redirects=True)
    with app.app_context():
        from app.models.platform import MediaAsset

        assert MediaAsset.query.filter_by(alt_text="Office lobby").first() is None


def test_admin_features_that_were_unwired(client, app):
    with app.app_context():
        _staff, password = create_staff("complete@neuralxpert.com")
    _open_dashboard(client, app, "complete@neuralxpert.com", password)

    menu = client.post(
        "/admin/navigation",
        data={"create": "1", "menu": "footer", "label": "Partner desk", "url": "/contact"},
        follow_redirects=True,
    )
    assert b"Partner desk" in menu.data
    assert b"New tab" in menu.data
    with app.app_context():
        from app.models.platform import NavItem

        item = NavItem.query.filter_by(label="Partner desk").one()
        item_id = item.id
    client.post(
        "/admin/navigation",
        data={"item_id": item_id, "menu": "footer", "label": "Partner desk", "url": "/contact", "enabled": "1", "new_tab": "1"},
        follow_redirects=True,
    )
    public = client.get("/")
    assert b'target="_blank" rel="noopener">Partner desk' in public.data

    added = client.post(
        "/admin/redirects",
        data={"source": "/legacy", "target": "/about", "status_code": "302"},
        follow_redirects=True,
    )
    assert b"/legacy" in added.data
    hopped = client.get("/legacy")
    assert hopped.status_code == 302
    assert hopped.headers["Location"].endswith("/about")

    insight = client.post(
        "/admin/insights/new",
        data={
            "title": "Featured briefing",
            "excerpt": "Shown first when featured",
            "content": "<p>Body</p>",
            "author": "Amina Hassan",
            "featured": "1",
            "status": "published",
            "new_category": "Field notes",
        },
        follow_redirects=True,
    )
    assert b"Insight saved." in insight.data
    with app.app_context():
        from app.models import Article, Category

        article = Article.query.filter_by(title="Featured briefing").one()
        assert article.author == "Amina Hassan"
        assert article.featured is True
        assert article.category.name == "Field notes"
        slug = article.slug
        article_id = article.id
        assert Category.query.filter_by(name="Field notes").one()
    detail = client.get(f"/insights/{slug}")
    assert b"Amina Hassan" in detail.data
    removed = client.post(f"/admin/insights/{article_id}", data={"delete": "1"}, follow_redirects=True)
    assert b"Insight removed." in removed.data

    opening = client.post(
        "/admin/careers/new",
        data={"title": "AI engineer", "description": "Build production systems", "status": "published", "closing_on": "2026-12-01"},
        follow_redirects=True,
    )
    assert b"Opening saved." in opening.data
    with app.app_context():
        from app.models import Job

        job = Job.query.filter_by(title="AI engineer").one()
        job_slug = job.slug
    career = client.get(f"/careers/{job_slug}")
    assert b"December 01, 2026" in career.data

    uploaded = client.post(
        "/admin/media",
        data={"alt_text": "Lobby measurement", "folder": "general", "file": (BytesIO(_PNG), "measure.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "1×1".encode() in uploaded.data
    found = client.get("/admin/search?q=Lobby+measurement")
    assert b"Lobby measurement" in found.data

    pages = client.get("/admin/pages")
    page_id = re.search(br"/admin/pages/(\d+)", pages.data).group(1).decode()
    client.post(f"/admin/pages/{page_id}", data={"title": "Alpha title", "hero_title": "Alpha title"})
    client.post(f"/admin/pages/{page_id}", data={"title": "Beta title", "hero_title": "Beta title"})
    with app.app_context():
        from app.models.platform import ContentRevision

        revision = ContentRevision.query.filter(ContentRevision.snapshot.contains("Alpha title")).order_by(ContentRevision.id.asc()).first()
        revision_id = revision.id
    restored = client.post("/admin/revisions", data={"restore_id": revision_id}, follow_redirects=True)
    assert b"Revision restored." in restored.data
    with app.app_context():
        from app.extensions import db
        from app.models.platform import SitePage

        assert db.session.get(SitePage, int(page_id)).title == "Alpha title"

    solution = client.post(
        "/admin/solutions/new",
        data={"name": "Custom widget", "summary": "Temporary", "status": "draft"},
        follow_redirects=True,
    )
    assert b"Solution saved." in solution.data
    with app.app_context():
        from app.models.platform import Offering

        item_id = Offering.query.filter_by(name="Custom widget").one().id
        seeded_id = Offering.query.filter_by(kind="solution", slug="generative-ai").one().id
    gone = client.post(f"/admin/solutions/{item_id}", data={"delete": "1"}, follow_redirects=True)
    assert b"Solution removed." in gone.data
    blocked = client.post(f"/admin/solutions/{seeded_id}", data={"delete": "1"})
    assert b"Built-in items come back if removed." in blocked.data

    with app.app_context():
        from app.models import StaffUser

        other, _password = create_staff("temp@neuralxpert.com")
        other_id = other.id
    reset = client.post(f"/admin/users/{other_id}", data={"action": "reset"}, follow_redirects=True)
    assert b"Temporary password" in reset.data
    assert b"temp@neuralxpert.com" in reset.data
    with app.app_context():
        from app.extensions import db
        from app.models import StaffUser

        person = StaffUser.query.filter_by(email="temp@neuralxpert.com").one()
        person.totp_enabled = True
        person.totp_secret = "secret"
        db.session.commit()
    cleared = client.post(f"/admin/users/{other_id}", data={"action": "reset_mfa"}, follow_redirects=True)
    assert b"Authenticator cleared." in cleared.data
    with app.app_context():
        from app.models import StaffUser

        assert StaffUser.query.filter_by(email="temp@neuralxpert.com").one().totp_enabled is False


def test_admin_styles_the_case_studies_page(client, app):
    with app.app_context():
        _staff, password = create_staff("cases@neuralxpert.com")
    _open_dashboard(client, app, "cases@neuralxpert.com", password)
    saved = client.post(
        "/admin/case-studies",
        data={
            "listing": "1",
            "title": "Our work",
            "hero_title": "Systems in production",
            "hero_subtitle": "FIELD NOTES",
            "summary": "A shorter introduction.",
            "cta_label": "Open the study",
            "font_family": "georgia",
            "heading_size": "40",
            "body_size": "18",
            "tag_size": "14",
            "heading_color": "#112233",
            "body_color": "#445566",
            "hero_width": "960",
            "hero_height": "420",
            "hero_image_file": (BytesIO(_PNG), "hero.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Case studies page updated." in saved.data
    created = client.post(
        "/admin/case-studies/new",
        data={
            "title": "Styled platform",
            "summary": "Card summary text",
            "status": "published",
            "font_family": "arial",
            "title_size": "28",
            "summary_size": "16",
            "image_width": "320",
            "image_height": "180",
            "image_radius": "8",
            "featured_image_file": (BytesIO(_PNG), "card.png"),
            "arch_width": "400",
            "arch_height": "200",
            "arch_radius": "12",
            "architecture_image_file": (BytesIO(_PNG), "arch.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Case study saved." in created.data
    page = client.get("/case-studies")
    assert b"Our work" in page.data
    assert b"Systems in production" in page.data
    assert b"FIELD NOTES" in page.data
    assert b"A shorter introduction." in page.data
    assert b"Georgia, serif" in page.data
    assert b"--nx-case-heading-size:40px" in page.data
    assert b"--nx-case-body-size:18px" in page.data
    assert b"#112233" in page.data
    assert b"Open the study" in page.data
    assert b"--nx-case-hero-width:960px" in page.data
    assert b"--nx-case-hero-height:420px" in page.data
    assert b"font-size:28px" in page.data
    assert b"font-size:16px" in page.data
    assert b"Arial, Helvetica, sans-serif" in page.data
    assert b"width:320px" in page.data
    assert b"height:180px" in page.data
    assert b"border-radius:8px" in page.data
    detail = client.get("/case-studies/styled-platform")
    assert detail.status_code == 200
    assert b"font-size:28px" in detail.data
    assert b"min-height:180px" in detail.data
    assert b"border-radius:8px" in detail.data
    assert b"width:400px" in detail.data
    assert b"border-radius:12px" in detail.data


def test_approved_records_appear_on_the_public_site(client, app):
    import os
    from datetime import date

    with app.app_context():
        from app.extensions import db
        from app.models import Job, JobApplication
        from app.models.platform import Credential, Partner, Testimonial

        db.session.add(Testimonial(customer="Amina", company="Northwind", quote="The deployment was careful.", approved=True, status="published"))
        db.session.add(Testimonial(customer="Hidden", quote="Do not publish this.", approved=False, status="draft"))
        db.session.add(Partner(name="Harbor Cloud", relationship="Technology", evidence="Contract 2026", display=True))
        db.session.add(Partner(name="Unapproved Labs", evidence="", display=True))
        db.session.add(Credential(name="ISO 27001", issuer="BSI", holder="Neural Xpert", display=True, status="active", expires_on=date(2027, 1, 1)))
        job = Job(title="Platform engineer", slug="platform-engineer", status="draft")
        db.session.add(job)
        db.session.flush()
        application = JobApplication(job=job, name="Nora", email="nora@example.com", cover_letter="I build platforms.", cv_filename="nora.pdf", cv_original_name="nora.pdf")
        db.session.add(application)
        db.session.commit()
        application_id = application.id
        folder = app.config["UPLOAD_FOLDER"]
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "nora.pdf"), "wb") as handle:
            handle.write(b"%PDF-1.4 test")
    home = client.get("/")
    assert b"The deployment was careful." in home.data
    assert b"Harbor Cloud" in home.data
    assert b"Do not publish this." not in home.data
    assert b"Unapproved Labs" not in home.data
    about = client.get("/about")
    assert b"ISO 27001" in about.data
    denied = client.get(f"/admin/applications/{application_id}/cv")
    assert denied.status_code in {302, 401, 403}
    with app.app_context():
        import time

        from app.admin.security import session_stamp
        from app.extensions import db

        staff, _password = create_staff("cv@neuralxpert.com")
        staff.totp_enabled = True
        staff.totp_secret = "JBSWY3DPEHPK3PXP"
        db.session.commit()
        stamp = session_stamp(staff)
        staff_id = staff.id
    now = int(time.time())
    with client.session_transaction() as sess:
        sess["staff_id"] = staff_id
        sess["mfa_complete"] = True
        sess["staff_seen"] = now
        sess["staff_started"] = now
        sess["staff_stamp"] = stamp
    downloaded = client.get(f"/admin/applications/{application_id}/cv")
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"%PDF")
    listed = client.get("/admin/applications")
    assert b"I build platforms." in listed.data
