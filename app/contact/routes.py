from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, render_template, request

from app.extensions import db, limiter
from app.limits import rate_limited
from app.mailer import notify_contact
from app.models import ContactSubmission
from app.services import seo_for

bp = Blueprint("contact", __name__)


@bp.route("/contact")
def index():
    context = seo_for(
        "contact",
        "Contact Neural Xpert",
        "Talk with Neural Xpert about enterprise AI, generative AI, AI agents, RAG, and production AI programs.",
    )
    return render_template("main/contact.html", **context)


@bp.route("/contact", methods=["POST"])
@limiter.limit("5 per minute")
def submit():
    if rate_limited("contact", 5, 60):
        return "Please wait a moment and try again.", 429
    if request.form.get("company_website"):
        return "Thank You! Your message has been sent.", 200

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("number", "").strip() or request.form.get("phone", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    company = request.form.get("company", "").strip()

    if not name or not message or not phone or not subject:
        return "Please complete the form and try again.", 400
    if len(name) > 120 or len(subject) > 160 or len(message) > 5000 or len(phone) > 50 or len(company) > 160:
        return "Please complete the form and try again.", 400
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return "Please complete the form and try again.", 400

    submission = ContactSubmission(
        name=name,
        company=company,
        email=email,
        phone=phone,
        subject=subject,
        message=message,
    )
    submission.source_page = (request.referrer or "")[:300]
    submission.utm_source = (request.form.get("utm_source") or request.args.get("utm_source") or "")[:160]
    submission.interest = (request.form.get("interest") or subject)[:160]
    db.session.add(submission)
    from app.admin.catalog import record_event

    record_event("contact_submit", "/contact", subject)
    db.session.commit()
    notify_contact(submission)
    return "Thank You! Your message has been sent.", 200
