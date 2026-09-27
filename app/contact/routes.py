from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, current_app, render_template, request
from flask_mail import Message

from app.extensions import db, limiter, mail
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
    db.session.add(submission)
    db.session.commit()
    _notify(submission)
    return "Thank You! Your message has been sent.", 200


def _notify(submission):
    if not current_app.config.get("MAIL_SERVER"):
        current_app.logger.info("Contact enquiry %s stored. Email delivery is not configured.", submission.id)
        return
    body = (
        f"Name: {submission.name}\n"
        f"Company: {submission.company}\n"
        f"Email: {submission.email}\n"
        f"Phone: {submission.phone}\n"
        f"Subject: {submission.subject}\n\n"
        f"{submission.message}\n"
    )
    message = Message(
        subject=f"New contact from {submission.subject}",
        recipients=[current_app.config["CONTACT_RECIPIENT"]],
        body=body,
        reply_to=submission.email,
    )
    try:
        mail.send(message)
    except Exception:
        current_app.logger.exception("Contact enquiry %s was stored but email failed.", submission.id)
