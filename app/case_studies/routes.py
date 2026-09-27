from flask import Blueprint, abort, render_template

from app.models import CaseStudy
from app.services import absolute_static, canonical_url, seo_for

bp = Blueprint("case_studies", __name__)


@bp.route("/case-studies")
def index():
    studies = (
        CaseStudy.query.filter_by(status="published")
        .order_by(CaseStudy.published_at.desc(), CaseStudy.id.desc())
        .all()
    )
    context = seo_for(
        "case-studies",
        "Case Studies | Neural Xpert",
        "Explore how Neural Xpert designs and delivers secure, production-ready AI solutions for the enterprise.",
    )
    return render_template("case_studies/list.html", studies=studies, **context)


@bp.route("/case-studies/<slug>")
def detail(slug):
    study = CaseStudy.query.filter_by(slug=slug, status="published").first()
    if study is None:
        abort(404)
    title = study.seo_title or f"{study.title} | Neural Xpert"
    description = study.meta_description or study.summary
    context = seo_for("case-study", title, description, study.featured_image)
    context["canonical_url"] = canonical_url(f"/case-studies/{study.slug}")
    context["og_type"] = "article"
    context["og_image"] = absolute_static(study.featured_image)
    return render_template("case_studies/detail.html", study=study, **context)
