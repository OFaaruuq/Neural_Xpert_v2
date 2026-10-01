from flask import Blueprint, abort, jsonify, render_template, request

from app.extensions import limiter
from app.limits import rate_limited
from app.services import seo_for

bp = Blueprint("main", __name__)

HOME_DESCRIPTION = (
    "Neural Xpert builds secure enterprise AI solutions, including Generative AI, AI agents, "
    "RAG, machine learning, intelligent automation, AI integration and AI security."
)
HOME_KEYWORDS = (
    "Neural Xpert, enterprise AI, AI solutions, Generative AI, GenAI, AI agents, agentic AI, RAG, "
    "Retrieval-Augmented Generation, machine learning, LLM applications, enterprise AI agents, "
    "AI automation, AI integration, AI consulting, AI development, MLOps, AI security, Responsible AI"
)


def render_page(template, page_key, title, description, **extra):
    context = seo_for(page_key, title, description)
    context.update(extra)
    return render_template(template, **context)


@bp.route("/")
def index():
    context = seo_for(
        "home",
        "Neural Xpert | Enterprise AI, Generative AI & AI Solutions",
        HOME_DESCRIPTION,
    )
    context["seo_keywords"] = HOME_KEYWORDS
    context["og_description"] = (
        "Build, deploy and scale secure enterprise AI with Neural Xpert. Generative AI, AI agents, "
        "RAG, machine learning, intelligent automation and AI security."
    )
    context["footer_variant"] = "home"
    return render_template("main/home.html", **context)


@bp.route("/about")
def about():
    return render_page(
        "main/about.html",
        "about",
        "About Neural Xpert | Enterprise AI",
        "Neural Xpert is an enterprise technology company focused on Artificial Intelligence, Cloud Engineering, and Cybersecurity.",
    )


def published_offerings(kind):
    try:
        from app.models.platform import Offering

        return Offering.query.filter_by(kind=kind, status="published").order_by(Offering.position, Offering.name).all()
    except Exception:
        return []


@bp.route("/solutions")
def solutions():
    return render_page(
        "main/solutions.html",
        "solutions",
        "AI Solutions | Neural Xpert",
        "Enterprise AI capabilities from Neural Xpert, including Generative AI, AI agents, RAG, machine learning, automation, and AI security.",
        published_solutions=published_offerings("solution"),
    )


@bp.route("/solutions/<slug>")
def solution_detail(slug):
    return _offering_detail("solution", slug)


@bp.route("/services")
def services():
    return render_page(
        "main/services.html",
        "services",
        "AI Services | Neural Xpert",
        "AI strategy, engineering, cloud infrastructure, cybersecurity, data integration, and MLOps services from Neural Xpert.",
        published_services=published_offerings("service"),
    )


@bp.route("/services/<slug>")
def service_detail(slug):
    return _offering_detail("service", slug)


@bp.route("/industries")
def industries():
    return render_page(
        "main/industries.html",
        "industries",
        "Industries | Neural Xpert",
        "Neural Xpert delivers production-ready enterprise AI across industries.",
        published_industries=published_offerings("industry"),
    )


@bp.route("/industries/<slug>")
def industry_detail(slug):
    return _offering_detail("industry", slug)


def _offering_detail(kind, slug):
    from app.admin.catalog import record_event
    from app.extensions import db
    from app.models.platform import Offering

    item = Offering.query.filter_by(kind=kind, slug=slug, status="published").first()
    if item is None:
        abort(404)
    public_path = {"solution": "solutions", "service": "services", "industry": "industries"}.get(kind, kind)
    record_event("offering_view", f"/{public_path}/{slug}", item.name)
    db.session.commit()
    context = seo_for(kind, item.seo_title or f"{item.name} | Neural Xpert", item.meta_description or item.summary, item.hero_image)
    return render_template("main/offering.html", item=item, **context)


@bp.route("/privacy-policy")
def privacy_policy():
    return render_page(
        "main/privacy_policy.html",
        "privacy",
        "Neural Xpert | Privacy Policy",
        "How Neural Xpert handles information collected through neuralxpert.com and related business inquiries.",
    )


@bp.route("/terms-of-service")
def terms_of_service():
    return render_page(
        "main/terms_of_service.html",
        "terms",
        "Neural Xpert | Terms of Service",
        "Terms that apply when you use the Neural Xpert website and related inquiry channels.",
    )


@bp.route("/ask-ai", methods=["POST"])
@limiter.limit("20 per hour")
def ask_ai():
    from app.ai_support import answer

    if rate_limited("ask-ai", 12, 600):
        return jsonify(error="Please wait a moment and try again."), 429
    reply, code = answer(request.get_json(silent=True) or {})
    if code == "disabled":
        return jsonify(error="ASK AI is not available."), 404
    if code == "unconfigured":
        return jsonify(error="ASK AI is not available."), 404
    if code == "invalid":
        return jsonify(error="Enter a message and try again."), 400
    if code == "busy":
        return jsonify(error="ASK AI is busy. Please try again in a moment."), 429
    if code:
        return jsonify(error="ASK AI could not answer just now. Please try again or contact us."), 502
    return jsonify(reply=reply)


@bp.route("/cookie-policy")
def cookie_policy():
    return render_page(
        "main/cookie_policy.html",
        "cookies",
        "Neural Xpert | Cookie Policy",
        "How Neural Xpert uses cookies and similar technologies on neuralxpert.com.",
    )
