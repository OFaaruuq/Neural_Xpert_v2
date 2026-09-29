import os
import uuid

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from app.extensions import db, limiter
from app.mailer import notify_application
from app.models import Job, JobApplication
from app.services import plain_excerpt, seo_for

bp = Blueprint("careers", __name__)


@bp.route("/careers")
def index():
    jobs = Job.query.filter(Job.status.in_(("published", "open"))).order_by(Job.published_at.desc(), Job.id.desc()).all()
    context = seo_for(
        "careers",
        "Neural Xpert | Careers",
        "Open roles at Neural Xpert for engineers, architects, and consultants who build production enterprise AI. Apply with a CV or write to the team.",
    )
    return render_template("main/careers.html", jobs=jobs, **context)


@bp.route("/careers/<slug>", methods=["GET", "POST"])
@limiter.limit("8 per hour", methods=["POST"])
def detail(slug):
    job = Job.query.filter(Job.slug == slug, Job.status.in_(("published", "open"))).first()
    if job is None:
        abort(404)
    errors = []
    if request.method == "POST":
        errors = _save_application(job)
        if not errors:
            flash("Thank you. Your application has been received.", "success")
            return redirect(url_for("careers.detail", slug=job.slug))
    summary = plain_excerpt(job.description, 160)
    context = seo_for("career", f"{job.title} | Neural Xpert Careers", summary or f"Apply for {job.title} at Neural Xpert.")
    context["robots"] = "index, follow"
    return render_template(
        "careers/detail.html",
        job=job,
        errors=errors,
        posting=_job_posting(job, plain_excerpt(job.description, 4000) or summary),
        **context,
    )


def _job_posting(job, summary):
    posted = job.published_at or job.created_at
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": summary or job.title,
        "hiringOrganization": {
            "@type": "Organization",
            "name": "Neural Xpert",
            "sameAs": current_app.config["SITE_URL"].rstrip("/"),
        },
        "directApply": True,
        "url": request.base_url,
    }
    if posted is not None:
        data["datePosted"] = posted.date().isoformat()
    employment = _employment_type(job.employment_type)
    if employment:
        data["employmentType"] = employment
    place = (job.location or "").strip()
    remote = (job.workplace or "").lower() == "remote" or place.lower() == "remote"
    if remote:
        data["jobLocationType"] = "TELECOMMUTE"
    if place and place.lower() != "remote":
        data["jobLocation"] = {
            "@type": "Place",
            "address": {"@type": "PostalAddress", "addressLocality": place},
        }
    if job.closing_on:
        data["validThrough"] = job.closing_on.isoformat()
    return data


def _employment_type(value):
    key = (value or "").strip().lower().replace("_", "-")
    return {
        "full-time": "FULL_TIME",
        "full time": "FULL_TIME",
        "part-time": "PART_TIME",
        "part time": "PART_TIME",
        "contract": "CONTRACTOR",
        "contractor": "CONTRACTOR",
        "internship": "INTERN",
        "temporary": "TEMPORARY",
    }.get(key)


def _save_application(job):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    cover_letter = request.form.get("cover_letter", "").strip()
    upload = request.files.get("cv")
    errors = []
    if not name or len(name) > 120:
        errors.append("Enter your full name.")
    if "@" not in email or len(email) > 255:
        errors.append("Enter a valid email address.")
    if len(phone) > 50:
        errors.append("Enter a shorter phone number.")
    if len(cover_letter) > 5000:
        errors.append("Cover letter is too long.")
    if upload is None or not upload.filename:
        errors.append("Attach a CV in PDF, DOC, or DOCX format.")
        return errors
    original = secure_filename(upload.filename)
    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if extension not in current_app.config["ALLOWED_CV_EXTENSIONS"]:
        errors.append("CV must be a PDF, DOC, or DOCX file.")
    header = upload.read(8)
    upload.seek(0)
    signatures = {
        "pdf": b"%PDF",
        "docx": b"PK",
        "doc": b"\xd0\xcf\x11\xe0",
    }
    expected = signatures.get(extension, b"")
    if expected and not header.startswith(expected):
        errors.append("CV must be a PDF, DOC, or DOCX file.")
    upload.seek(0, os.SEEK_END)
    size = upload.tell()
    upload.seek(0)
    if size > 5 * 1024 * 1024:
        errors.append("CV must be 5 MB or smaller.")
    if errors:
        return errors
    stored = f"{uuid.uuid4().hex}.{extension}"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    upload.save(os.path.join(folder, stored))
    application = JobApplication(
        job=job,
        name=name,
        email=email,
        phone=phone,
        cover_letter=cover_letter,
        cv_filename=stored,
        cv_original_name=original,
    )
    db.session.add(application)
    db.session.commit()
    notify_application(job, application)
    return []
