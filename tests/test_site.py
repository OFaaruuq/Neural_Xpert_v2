import io

import pytest

from app import create_app
from app.extensions import db
from app.models import Job, User
from app.seed import seed


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        seed()
        admin = User(email="admin@neuralxpert.com", role="admin")
        admin.set_password("correct-horse")
        db.session.add(admin)
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_keeps_frontend_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Build Intelligence Into Your Enterprise" in html
    assert "/static/css/style.css" in html
    assert "/static/js/main.js" in html
    assert 'href="index.html"' not in html
    assert "mail.php" not in html
    assert 'footer-layout1 style2' in html


def test_inner_pages_and_clean_urls(client):
    for path in ["/about", "/solutions", "/services", "/industries", "/case-studies", "/insights", "/careers", "/contact", "/privacy-policy", "/terms-of-service", "/cookie-policy"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"mail.php" not in response.data


def test_legacy_redirects(client):
    response = client.get("/blog.html", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/insights")
    response = client.get("/blog-rathat.html", follow_redirects=False)
    assert response.status_code == 301
    assert "/insights/rathat-android-trojan-uses-ai-for-automation" in response.headers["Location"]


def test_insights_are_database_driven(client):
    response = client.get("/insights")
    assert response.status_code == 200
    assert b"RatHat Android Trojan Uses AI for Automation" in response.data
    detail = client.get("/insights/rathat-android-trojan-uses-ai-for-automation")
    assert detail.status_code == 200
    assert b"Zimperium" in detail.data
    missing = client.get("/insights/not-a-real-article")
    assert missing.status_code == 404


def test_case_study_detail(client):
    response = client.get("/case-studies/enterprise-ai-knowledge-assistant")
    assert response.status_code == 200
    assert b"Enterprise AI Knowledge Assistant" in response.data


def test_contact_submission(client, app):
    response = client.post(
        "/contact",
        data={"name": "Ada Lovelace", "email": "ada@example.com", "number": "123", "subject": "AI", "message": "Hello"},
    )
    assert response.status_code == 200
    assert b"Thank You" in response.data
    from app.models import ContactSubmission

    with app.app_context():
        assert ContactSubmission.query.count() == 1
    rejected = client.post("/contact", data={"name": "", "email": "ada@example.com", "number": "", "subject": "", "message": ""})
    assert rejected.status_code == 400


def test_admin_is_private_and_has_no_registration(client):
    assert client.get("/admin").status_code == 302
    assert client.get("/admin/register").status_code == 404
    login = client.post("/admin/login", data={"email": "admin@neuralxpert.com", "password": "wrong"})
    assert b"Invalid email or password" in login.data
    success = client.post("/admin/login", data={"email": "admin@neuralxpert.com", "password": "correct-horse"}, follow_redirects=True)
    assert b"Dashboard" in success.data


def test_job_application_rejects_bad_files(client, app):
    with app.app_context():
        job = Job(
            title="AI Engineer",
            slug="ai-engineer",
            department="Engineering",
            location="Remote",
            employment_type="Full-time",
            description="Build production AI.",
            requirements="Python",
            status="published",
        )
        db.session.add(job)
        db.session.commit()
    page = client.get("/careers/ai-engineer")
    assert page.status_code == 200
    bad = client.post(
        "/careers/ai-engineer",
        data={"name": "Grace", "email": "grace@example.com", "phone": "1", "cover_letter": "Hi", "cv": (io.BytesIO(b"MZ"), "cv.exe")},
        content_type="multipart/form-data",
    )
    assert b"PDF" in bad.data
    good = client.post(
        "/careers/ai-engineer",
        data={"name": "Grace", "email": "grace@example.com", "phone": "1", "cover_letter": "Hi", "cv": (io.BytesIO(b"%PDF-1.4"), "cv.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"received" in good.data


def test_sitemap_and_robots(client):
    robots = client.get("/robots.txt")
    assert b"Sitemap:" in robots.data
    assert b"Disallow: /admin" in robots.data
    sitemap = client.get("/sitemap.xml")
    assert b"/insights/rathat-android-trojan-uses-ai-for-automation" in sitemap.data


def test_production_config_is_not_debug():
    from config import ProductionConfig

    assert ProductionConfig.DEBUG is False
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
