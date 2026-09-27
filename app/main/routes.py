from flask import Blueprint, render_template

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


@bp.route("/solutions")
def solutions():
    return render_page(
        "main/solutions.html",
        "solutions",
        "AI Solutions | Neural Xpert",
        "Enterprise AI capabilities from Neural Xpert, including Generative AI, AI agents, RAG, machine learning, automation, and AI security.",
    )


@bp.route("/services")
def services():
    return render_page(
        "main/services.html",
        "services",
        "AI Services | Neural Xpert",
        "AI strategy, engineering, cloud infrastructure, cybersecurity, data integration, and MLOps services from Neural Xpert.",
    )


@bp.route("/industries")
def industries():
    return render_page(
        "main/industries.html",
        "industries",
        "Industries | Neural Xpert",
        "Neural Xpert delivers production-ready enterprise AI across industries.",
    )


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


@bp.route("/cookie-policy")
def cookie_policy():
    return render_page(
        "main/cookie_policy.html",
        "cookies",
        "Neural Xpert | Cookie Policy",
        "How Neural Xpert uses cookies and similar technologies on neuralxpert.com.",
    )
