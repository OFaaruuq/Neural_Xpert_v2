import re

from flask import Blueprint, abort, render_template, request

from app.models import Article, Category
from app.services import absolute_static, canonical_url, seo_for

bp = Blueprint("blog", __name__)


def reading_minutes(article):
    text = re.sub(r"<[^>]+>", " ", f"{article.excerpt or ''} {article.content or ''}")
    words = len(text.split())
    return max(1, -(-words // 200))


@bp.route("/insights")
def index():
    page = request.args.get("page", 1, type=int)
    category_slug = request.args.get("category", "")
    search = (request.args.get("q") or "").strip()
    query = Article.query.filter_by(status="published")
    active_category = None
    if search:
        safe = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{safe}%"
        query = query.filter(
            Article.title.ilike(like, escape="\\")
            | Article.excerpt.ilike(like, escape="\\")
            | Article.content.ilike(like, escape="\\")
        )
    if category_slug:
        active_category = Category.query.filter_by(slug=category_slug, kind="article").first()
        if active_category:
            query = query.filter_by(category_id=active_category.id)
    pagination = query.order_by(Article.published_at.desc(), Article.id.desc()).paginate(page=page, per_page=6)
    categories = Category.query.filter_by(kind="article").order_by(Category.name).all()
    context = seo_for(
        "insights",
        "Neural Xpert | Enterprise AI Insights",
        "Insights on enterprise AI, generative AI, AI agents, RAG, machine learning, and AI security from Neural Xpert.",
    )
    return render_template(
        "blog/list.html",
        articles=pagination.items,
        pagination=pagination,
        categories=categories,
        active_category=active_category,
        search=search,
        **context,
    )


@bp.route("/insights/<slug>")
def detail(slug):
    article = Article.query.filter_by(slug=slug, status="published").first()
    if article is None:
        abort(404)
    recent = (
        Article.query.filter(Article.status == "published", Article.id != article.id)
        .order_by(Article.published_at.desc())
        .limit(3)
        .all()
    )
    categories = Category.query.filter_by(kind="article").order_by(Category.name).all()
    title = article.seo_title or f"{article.title} | Neural Xpert"
    description = article.meta_description or article.excerpt
    image = article.og_image or article.featured_image
    context = seo_for("article", title, description, image)
    context["canonical_url"] = canonical_url(f"/insights/{article.slug}")
    context["og_type"] = "article"
    context["og_image"] = absolute_static(image)
    return render_template(
        "blog/detail.html",
        article=article,
        recent_articles=recent,
        categories=categories,
        reading_minutes=reading_minutes(article),
        **context,
    )
