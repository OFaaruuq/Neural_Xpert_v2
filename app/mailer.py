import os
import re
from html import escape

from flask import current_app
from flask_mail import Message
from markupsafe import Markup

from app.extensions import mail

_CV_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


CONTACT_SUBJECT = "We received your message"
CONTACT_BODY = (
    "Hello {name},\n\n"
    "Thank you for contacting Neural Xpert. We have received your message "
    "about {subject}, and a member of the team will reply to this email address.\n\n"
    "Neural Xpert"
)
CAREER_SUBJECT = "We received your application for {job}"
CAREER_BODY = (
    "Hello {name},\n\n"
    "Thank you for applying for {job} at Neural Xpert. "
    "We have received your application and will be in touch if your experience matches the role.\n\n"
    "Neural Xpert"
)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _fill(template, **values):
    text = template or ""
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value or ""))
    return text


def _saved(key):
    try:
        from app.admin.catalog import setting_value

        return setting_value(key)
    except Exception:
        current_app.logger.debug("Mail settings are unavailable")
        return ""


def apply_mail_settings():
    """A saved SMTP server replaces the environment. A blank server keeps the environment."""
    server = _saved("mail_server")
    if server:
        current_app.config["MAIL_SERVER"] = server
        port = _saved("mail_port")
        if port.isdigit():
            current_app.config["MAIL_PORT"] = int(port)
        tls = _saved("mail_use_tls")
        if tls in {"0", "1"}:
            current_app.config["MAIL_USE_TLS"] = tls == "1"
        ssl = _saved("mail_use_ssl")
        if ssl in {"0", "1"}:
            current_app.config["MAIL_USE_SSL"] = ssl == "1"
        username = _saved("mail_username")
        if username:
            current_app.config["MAIL_USERNAME"] = username
        password = _saved("mail_password")
        if password:
            current_app.config["MAIL_PASSWORD"] = password
        sender = _saved("mail_sender")
        if sender:
            current_app.config["MAIL_DEFAULT_SENDER"] = sender
    recipient = _saved("mail_recipient")
    if recipient:
        current_app.config["MAIL_DEFAULT_RECIPIENT"] = recipient
        current_app.config["CONTACT_RECIPIENT"] = recipient


def mail_form_state():
    apply_mail_settings()
    config = current_app.config
    return {
        "server": config.get("MAIL_SERVER") or "",
        "port": config.get("MAIL_PORT") or 587,
        "tls": bool(config.get("MAIL_USE_TLS")),
        "ssl": bool(config.get("MAIL_USE_SSL")),
        "username": config.get("MAIL_USERNAME") or "",
        "sender": config.get("MAIL_DEFAULT_SENDER") or "Neural Xpert",
        "recipient": mail_recipient() or "",
        "password_set": bool(config.get("MAIL_PASSWORD")),
        "password_saved": bool(_saved("mail_password")),
        "using_saved": bool(_saved("mail_server")),
        "contact_subject": _saved("mail_contact_subject") or CONTACT_SUBJECT,
        "contact_body": _saved("mail_contact_body") or CONTACT_BODY,
        "career_subject": _saved("mail_career_subject") or CAREER_SUBJECT,
        "career_body": _saved("mail_career_body") or CAREER_BODY,
    }


def _flag(form, name):
    values = form.getlist(name) if hasattr(form, "getlist") else [form.get(name)]
    return "1" if values and values[-1] == "1" else "0"


def _put(key, value):
    from app.models.platform import SiteSetting

    from app.extensions import db

    row = SiteSetting.query.filter_by(key=key).first()
    if row is None:
        row = SiteSetting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value


def save_mail_settings(form):
    server = (form.get("mail_server") or "").strip()
    port = (form.get("mail_port") or "").strip()
    username = (form.get("mail_username") or "").strip()
    sender = (form.get("mail_sender") or "").strip()
    recipient = (form.get("mail_recipient") or "").strip()
    password = form.get("mail_password") or ""
    tls = _flag(form, "mail_use_tls")
    ssl = _flag(form, "mail_use_ssl")
    if server and (" " in server or len(server) > 255):
        return "Enter a valid SMTP server."
    if port and (not port.isdigit() or not 1 <= int(port) <= 65535):
        return "Enter a port between 1 and 65535."
    if tls == "1" and ssl == "1":
        return "Use either TLS or SSL, not both."
    if username and not _EMAIL.fullmatch(username):
        return "Enter the mailbox address used to sign in to the SMTP server."
    if recipient and not _EMAIL.fullmatch(recipient):
        return "Enter a valid inbox address for website messages."
    if len(password) > 200:
        return "The password is too long."
    _put("mail_server", server[:255])
    _put("mail_port", port or "587")
    _put("mail_use_tls", tls)
    _put("mail_use_ssl", ssl)
    _put("mail_username", username[:255])
    _put("mail_sender", (sender or "Neural Xpert")[:255])
    _put("mail_recipient", recipient[:255])
    if password:
        _put("mail_password", password)
    _put("mail_contact_subject", (form.get("mail_contact_subject") or "")[:200])
    _put("mail_contact_body", (form.get("mail_contact_body") or "")[:4000])
    _put("mail_career_subject", (form.get("mail_career_subject") or "")[:200])
    _put("mail_career_body", (form.get("mail_career_body") or "")[:4000])
    return ""


def send_test_to(address):
    apply_mail_settings()
    if not current_app.config.get("MAIL_SERVER"):
        return False, "Add an SMTP server before sending a test."
    if not _EMAIL.fullmatch(address or ""):
        return False, "The signed-in account needs an email address for the test."
    sent = send_email(
        "Neural Xpert email test",
        [address],
        "This is a test from the Neural Xpert admin. Sign-in codes, contact messages, and career applications use this mailbox.\n",
        html=_email_html(
            "Email test",
            "Neural Xpert can send mail from this mailbox.",
            _paragraphs(
                "This is a test from the Neural Xpert admin.\n\n"
                "Sign-in codes, contact messages, and career applications use this mailbox."
            ),
        ),
    )
    if sent:
        return True, f"Test email sent to {address}."
    detail = getattr(g_safe_error(), "text", "")
    if detail:
        return False, f"The test email could not be sent. {detail}"
    return False, "The test email could not be sent. Check the server, port, username, and password."


def g_safe_error():
    return current_app.extensions.get("mail_last_error")


def _remember_error(exc):
    text = str(exc)
    password = current_app.config.get("MAIL_PASSWORD") or ""
    if password and password in text:
        text = text.replace(password, "••••")
    current_app.extensions["mail_last_error"] = type("MailError", (), {"text": text[:300]})()


def mail_sender():
    apply_mail_settings()
    raw = (current_app.config.get("MAIL_DEFAULT_SENDER") or "").strip()
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    if "@" in raw:
        return raw
    address = username or current_app.config.get("CONTACT_RECIPIENT") or "partnerships@neuralxpert.com"
    name = raw or "Neural Xpert"
    return (name, address)


def mail_recipient():
    apply_mail_settings()
    return (
        current_app.config.get("MAIL_DEFAULT_RECIPIENT")
        or current_app.config.get("CONTACT_RECIPIENT")
        or current_app.config.get("MAIL_USERNAME")
    )


def _site_url():
    return (current_app.config.get("SITE_URL") or "https://www.neuralxpert.com").rstrip("/")


def _paragraphs(text):
    chunks = [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]
    style = "margin:0 0 14px;font-family:Arial, Helvetica, sans-serif;font-size:16px;line-height:1.55;color:#484848;"
    return "".join(f'<p style="{style}">{escape(part).replace(chr(10), "<br>")}</p>' for part in chunks)


def _details(rows):
    cells = []
    for label, value in rows:
        cells.append(
            "<tr>"
            f'<td width="108" style="width:108px;padding:8px 16px 8px 0;font-family:Arial, Helvetica, sans-serif;font-size:13px;line-height:1.4;color:#8B8B8B;vertical-align:top;">{escape(label)}</td>'
            f'<td style="padding:8px 0;font-family:Arial, Helvetica, sans-serif;font-size:15px;line-height:1.45;color:#06050B;">{escape(value or "—")}</td>'
            "</tr>"
        )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;">{"".join(cells)}</table>'


def _email_html(title, preheader, inner):
    template = current_app.jinja_env.get_template("email/message.html")
    return template.render(
        title=title,
        preheader=preheader,
        inner=Markup(inner),
        site_url=_site_url(),
    )


def send_email(subject, recipients, body, reply_to=None, attachments=None, html=None):
    apply_mail_settings()
    current_app.extensions.pop("mail_last_error", None)
    if not current_app.config.get("MAIL_SERVER"):
        current_app.logger.info("Email not sent (%s). MAIL_SERVER is unset.", subject)
        return False
    inbox = [address for address in recipients if address]
    if not inbox:
        current_app.logger.error("Email not sent (%s). No recipient is configured.", subject)
        return False
    message = Message(
        subject=subject,
        recipients=inbox,
        body=body,
        html=html,
        sender=mail_sender(),
        reply_to=reply_to,
    )
    for filename, content_type, data in attachments or []:
        message.attach(filename, content_type, data)
    try:
        mail.send(message)
        return True
    except Exception as exc:
        _remember_error(exc)
        current_app.logger.exception("Email failed: %s", subject)
        return False


def send_sign_in_code(email, code, minutes):
    plain = (
        f"Your Neural Xpert admin sign-in code is {code}.\n"
        f"It expires in {minutes} minutes.\n\n"
        "After this code, sign-in asks for Google Authenticator.\n\n"
        "If you did not try to sign in, you can ignore this email.\n"
    )
    code_style = (
        "margin:8px 0 18px;padding:16px 12px;background:#F5F5F5;border-radius:12px;"
        "font-family:Arial, Helvetica, sans-serif;font-size:32px;line-height:1.2;"
        "letter-spacing:8px;font-weight:700;color:#06050B;text-align:center;"
    )
    inner = (
        _paragraphs("Use this code to continue signing in to the Neural Xpert admin.")
        + f'<p style="{code_style}">{escape(code)}</p>'
        + _paragraphs(
            f"It expires in {minutes} minutes. After this code, sign-in asks for Google Authenticator.\n\n"
            "If you did not try to sign in, you can ignore this email."
        )
    )
    return send_email(
        subject="Your Neural Xpert sign-in code",
        recipients=[email],
        body=plain,
        html=_email_html("Your sign-in code", f"Your Neural Xpert sign-in code is {code}.", inner),
    )


def notify_contact(submission):
    staff = (
        f"Name: {submission.name}\n"
        f"Company: {submission.company or '-'}\n"
        f"Email: {submission.email}\n"
        f"Phone: {submission.phone}\n"
        f"Subject: {submission.subject}\n\n"
        f"{submission.message}\n"
    )
    notice = (
        _paragraphs("A new message arrived from the website contact form.")
        + _details([
            ("Name", submission.name),
            ("Company", submission.company),
            ("Email", submission.email),
            ("Phone", submission.phone),
            ("Subject", submission.subject),
        ])
        + _paragraphs(submission.message)
    )
    send_email(
        subject=f"Neural Xpert contact: {submission.subject}",
        recipients=[mail_recipient()],
        body=staff,
        reply_to=submission.email,
        html=_email_html("New contact request", f"{submission.name} wrote about {submission.subject}.", notice),
    )
    reply = _fill(
        _saved("mail_contact_body") or CONTACT_BODY,
        name=submission.name,
        subject=submission.subject,
    )
    send_email(
        subject=_fill(_saved("mail_contact_subject") or CONTACT_SUBJECT, name=submission.name, subject=submission.subject),
        recipients=[submission.email],
        body=reply,
        html=_email_html("We received your message", "Thank you for contacting Neural Xpert.", _paragraphs(reply)),
    )


def notify_application(job, application):
    staff = (
        f"Role: {job.title}\n"
        f"Name: {application.name}\n"
        f"Email: {application.email}\n"
        f"Phone: {application.phone or '-'}\n\n"
        f"{application.cover_letter or '-'}\n"
    )
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], application.cv_filename)
    attachments = []
    if os.path.isfile(path):
        extension = application.cv_filename.rsplit(".", 1)[-1].lower()
        with open(path, "rb") as handle:
            attachments.append(
                (
                    application.cv_original_name or application.cv_filename,
                    _CV_TYPES.get(extension, "application/octet-stream"),
                    handle.read(),
                )
            )
    notice = (
        _paragraphs("A new application arrived from the careers page.")
        + _details([
            ("Role", job.title),
            ("Name", application.name),
            ("Email", application.email),
            ("Phone", application.phone),
            ("CV", "Attached" if attachments else "Not attached"),
        ])
        + _paragraphs(application.cover_letter or "")
    )
    send_email(
        subject=f"Career application: {job.title}",
        recipients=[mail_recipient()],
        body=staff,
        reply_to=application.email,
        attachments=attachments,
        html=_email_html("New career application", f"{application.name} applied for {job.title}.", notice),
    )
    reply = _fill(
        _saved("mail_career_body") or CAREER_BODY,
        name=application.name,
        job=job.title,
    )
    send_email(
        subject=_fill(_saved("mail_career_subject") or CAREER_SUBJECT, name=application.name, job=job.title),
        recipients=[application.email],
        body=reply,
        html=_email_html("Application received", f"We received your application for {job.title}.", _paragraphs(reply)),
    )
