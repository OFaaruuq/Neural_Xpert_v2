import os

from flask import current_app
from flask_mail import Message

from app.extensions import mail

_CV_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def mail_sender():
    raw = (current_app.config.get("MAIL_DEFAULT_SENDER") or "").strip()
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    if "@" in raw:
        return raw
    address = username or current_app.config.get("CONTACT_RECIPIENT") or "partnerships@neuralxpert.com"
    name = raw or "Neural Xpert"
    return (name, address)


def mail_recipient():
    return (
        current_app.config.get("MAIL_DEFAULT_RECIPIENT")
        or current_app.config.get("CONTACT_RECIPIENT")
        or current_app.config.get("MAIL_USERNAME")
    )


def send_email(subject, recipients, body, reply_to=None, attachments=None):
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
        sender=mail_sender(),
        reply_to=reply_to,
    )
    for filename, content_type, data in attachments or []:
        message.attach(filename, content_type, data)
    try:
        mail.send(message)
        return True
    except Exception:
        current_app.logger.exception("Email failed: %s", subject)
        return False


def notify_contact(submission):
    staff = (
        f"Name: {submission.name}\n"
        f"Company: {submission.company or '-'}\n"
        f"Email: {submission.email}\n"
        f"Phone: {submission.phone}\n"
        f"Subject: {submission.subject}\n\n"
        f"{submission.message}\n"
    )
    send_email(
        subject=f"Neural Xpert contact: {submission.subject}",
        recipients=[mail_recipient()],
        body=staff,
        reply_to=submission.email,
    )
    send_email(
        subject="We received your message",
        recipients=[submission.email],
        body=(
            f"Hello {submission.name},\n\n"
            "Thank you for contacting Neural Xpert. We have received your message "
            f"about {submission.subject} and will reply to this email address.\n\n"
            "Neural Xpert\n"
            "https://www.neuralxpert.com\n"
        ),
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
    send_email(
        subject=f"Career application: {job.title}",
        recipients=[mail_recipient()],
        body=staff,
        reply_to=application.email,
        attachments=attachments,
    )
    send_email(
        subject=f"We received your application for {job.title}",
        recipients=[application.email],
        body=(
            f"Hello {application.name},\n\n"
            f"Thank you for applying for {job.title} at Neural Xpert. "
            "We have received your application and will be in touch if your experience matches the role.\n\n"
            "Neural Xpert\n"
            "https://www.neuralxpert.com\n"
        ),
    )
