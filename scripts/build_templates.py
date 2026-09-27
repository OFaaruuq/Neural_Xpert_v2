"""Split the approved static pages into Jinja templates without rewriting layout."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "legacy" / "html"
OUT = ROOT / "app" / "templates"

ARTICLE_SLUGS = {
    "RatHat Android Trojan Uses AI for Automation": "rathat-android-trojan-uses-ai-for-automation",
    "Building Production-Ready Generative AI for the Enterprise": "building-production-ready-generative-ai-for-the-enterprise",
    "Designing AI Agents That Run Enterprise Workflows": "designing-ai-agents-that-run-enterprise-workflows",
    "Connecting Enterprise Knowledge with Secure RAG": "connecting-enterprise-knowledge-with-secure-rag",
    "Securing AI Systems from Design Through Production": "securing-ai-systems-from-design-through-production",
    "Moving Machine Learning from Pilots into Operations": "moving-machine-learning-from-pilots-into-operations",
    "Integrating AI with Enterprise Applications and Data": "integrating-ai-with-enterprise-applications-and-data",
}

CASE_SLUGS = {
    "Enterprise AI Knowledge Assistant": "enterprise-ai-knowledge-assistant",
    "AI-Powered Customer Service Automation": "ai-powered-customer-service-automation",
    "Intelligent Document Processing": "intelligent-document-processing",
    "AI Agents for Business Process Automation": "ai-agents-for-business-process-automation",
    "Predictive Intelligence Platform": "predictive-intelligence-platform",
    "Production AI Platform": "production-ai-platform",
}

ANCHOR_ROUTES = {
    "index.html#features-sec": "{{ url_for('main.solutions') }}",
    "index.html#services-sec": "{{ url_for('main.services') }}",
    "index.html#industries-sec": "{{ url_for('main.industries') }}",
    "index.html#generative-ai": "{{ url_for('main.solutions') }}#generative-ai",
    "index.html#ai-agents": "{{ url_for('main.solutions') }}#ai-agents",
    "index.html#enterprise-rag": "{{ url_for('main.solutions') }}#enterprise-rag",
    "index.html#machine-learning": "{{ url_for('main.solutions') }}#machine-learning",
    "index.html#intelligent-automation": "{{ url_for('main.solutions') }}#intelligent-automation",
    "index.html#ai-security": "{{ url_for('main.solutions') }}#ai-security",
    "index.html#cloud-infrastructure": "{{ url_for('main.services') }}#cloud-infrastructure",
    "index.html#cybersecurity": "{{ url_for('main.services') }}#cybersecurity",
    "index.html#data-integration": "{{ url_for('main.services') }}#data-integration",
    "index.html#mlops": "{{ url_for('main.services') }}#mlops",
}

PAGE_HREFS = {
    "index.html": "{{ url_for('main.index') }}",
    "about.html": "{{ url_for('main.about') }}",
    "case-studies.html": "{{ url_for('case_studies.index') }}",
    "blog.html": "{{ url_for('blog.index') }}",
    "careers.html": "{{ url_for('careers.index') }}",
    "contact.html": "{{ url_for('contact.index') }}",
    "privacy-policy.html": "{{ url_for('main.privacy_policy') }}",
    "terms-of-service.html": "{{ url_for('main.terms_of_service') }}",
    "cookie-policy.html": "{{ url_for('main.cookie_policy') }}",
    "features.html": "{{ url_for('main.solutions') }}",
    "home-ai-startup.html": "{{ url_for('main.index') }}",
    "error.html": "{{ url_for('main.index') }}",
}


def rewrite(html: str) -> str:
    def asset(match: re.Match) -> str:
        attr, path = match.group(1), match.group(2)
        return f"{attr}=\"{{{{ url_for('static', filename='{path}') }}}}\""

    html = re.sub(r'(href|src|data-bg-src|content)="assets/([^"]+)"', asset, html)

    for old, new in ANCHOR_ROUTES.items():
        html = html.replace(f'href="{old}"', f'href="{new}"')

    html = re.sub(
        r'href="index\.html(#[^"]+)"',
        r"href=\"{{ url_for('main.index') }}\1\"",
        html,
    )

    for old, new in PAGE_HREFS.items():
        html = html.replace(f'href="{old}"', f'href="{new}"')

    html = html.replace('action="mail.php"', "action=\"{{ url_for('contact.submit') }}\"")
    html = bind_content_links(html)
    return html


def bind_content_links(html: str) -> str:
    pattern = re.compile(
        r'href="(blog-details\.html|blog-rathat\.html|case-studies-details\.html)"([^>]*)>(.*?)</a>',
        re.S,
    )
    last = {"blog": None, "case": None}

    def repl(match: re.Match) -> str:
        kind = match.group(1)
        attrs = match.group(2)
        inner = match.group(3)
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
        if kind.startswith("blog"):
            slug = ARTICLE_SLUGS.get(label) or last["blog"]
            if label in ARTICLE_SLUGS:
                last["blog"] = slug
            if slug and label.lower() not in {"read more"} or label in ARTICLE_SLUGS:
                if slug:
                    href = "{{ url_for('blog.detail', slug='%s') }}" % slug
                else:
                    href = "{{ url_for('blog.index') }}"
            else:
                href = "{{ url_for('blog.detail', slug='%s') }}" % slug if slug else "{{ url_for('blog.index') }}"
        else:
            slug = CASE_SLUGS.get(label) or last["case"]
            if label in CASE_SLUGS:
                last["case"] = slug
            href = (
                "{{ url_for('case_studies.detail', slug='%s') }}" % slug
                if slug
                else "{{ url_for('case_studies.index') }}"
            )
        return f'href="{href}"{attrs}>{inner}</a>'

    return pattern.sub(repl, html)


def split_document(text: str):
    _, rest = text.split("<body>", 1)
    chrome, rest = rest.split("</header>", 1)
    chrome = chrome + "</header>"
    body, rest = rest.split("<footer", 1)
    footer_and_more = "<footer" + rest
    marker = "<!--==============================\n    All Js File"
    if marker not in footer_and_more:
        marker = "<!--==============================\r\n    All Js File"
    footer, scripts = footer_and_more.split(marker, 1)
    scripts = marker + scripts
    scripts = scripts.split("</body>", 1)[0]
    return chrome, body, footer, scripts


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(path.relative_to(ROOT), "bytes", len(content))


def main() -> None:
    index = (SRC / "index.html").read_text(encoding="utf-8")
    chrome, home_body, home_footer, scripts = split_document(index)
    inner = (SRC / "careers.html").read_text(encoding="utf-8")
    _, _, inner_footer, _ = split_document(inner)

    write(OUT / "includes" / "navbar.html", rewrite(chrome).strip() + "\n")
    write(
        OUT / "includes" / "footer.html",
        "{% if footer_variant == 'home' %}\n"
        + rewrite(home_footer).strip()
        + "\n{% else %}\n"
        + rewrite(inner_footer).strip()
        + "\n{% endif %}\n",
    )
    write(OUT / "includes" / "scripts.html", rewrite(scripts).strip() + "\n")

    head = """    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link rel="apple-touch-icon" sizes="57x57" href="{{ url_for('static', filename='img/favicons/apple-icon-57x57.png') }}">
    <link rel="apple-touch-icon" sizes="60x60" href="{{ url_for('static', filename='img/favicons/apple-icon-60x60.png') }}">
    <link rel="apple-touch-icon" sizes="72x72" href="{{ url_for('static', filename='img/favicons/apple-icon-72x72.png') }}">
    <link rel="apple-touch-icon" sizes="76x76" href="{{ url_for('static', filename='img/favicons/apple-icon-76x76.png') }}">
    <link rel="apple-touch-icon" sizes="114x114" href="{{ url_for('static', filename='img/favicons/apple-icon-114x114.png') }}">
    <link rel="apple-touch-icon" sizes="120x120" href="{{ url_for('static', filename='img/favicons/apple-icon-120x120.png') }}">
    <link rel="apple-touch-icon" sizes="144x144" href="{{ url_for('static', filename='img/favicons/apple-icon-144x144.png') }}">
    <link rel="apple-touch-icon" sizes="152x152" href="{{ url_for('static', filename='img/favicons/apple-icon-152x152.png') }}">
    <link rel="apple-touch-icon" sizes="180x180" href="{{ url_for('static', filename='img/favicons/apple-icon-180x180.png') }}">
    <link rel="icon" type="image/png" sizes="192x192" href="{{ url_for('static', filename='img/favicons/android-icon-192x192.png') }}">
    <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', filename='img/favicons/favicon-32x32.png') }}">
    <link rel="icon" type="image/png" sizes="96x96" href="{{ url_for('static', filename='img/favicons/favicon-96x96.png') }}">
    <link rel="icon" type="image/png" sizes="16x16" href="{{ url_for('static', filename='img/favicons/favicon-16x16.png') }}">
    <link rel="manifest" href="{{ url_for('static', filename='img/favicons/manifest.json') }}">
    <meta name="msapplication-TileColor" content="#ffffff">
    <meta name="msapplication-TileImage" content="{{ url_for('static', filename='img/favicons/ms-icon-144x144.png') }}">
    <meta name="theme-color" content="#ffffff">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Sora:wght@100..800&family=Urbanist:ital,wght@0,100..900;1,100..900&family=Work+Sans:ital,wght@0,100..900;1,100..900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/bootstrap.min.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/fontawesome.min.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/magnific-popup.min.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/swiper-bundle.min.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
"""
    write(OUT / "includes" / "head.html", head)

    seo = """    <title>{{ seo_title }}</title>
    <meta name="author" content="Neural Xpert">
    <meta name="description" content="{{ meta_description }}">
    {% if seo_keywords %}
    <meta name="keywords" content="{{ seo_keywords }}">
    {% endif %}
    <meta name="robots" content="{{ robots }}">
    <meta name="googlebot" content="{{ robots }}">
    <link rel="canonical" href="{{ canonical_url }}">
    <meta property="og:type" content="{{ og_type }}">
    <meta property="og:title" content="{{ og_title or seo_title }}">
    <meta property="og:description" content="{{ og_description or meta_description }}">
    <meta property="og:url" content="{{ canonical_url }}">
    <meta property="og:site_name" content="Neural Xpert">
    {% if og_image %}
    <meta property="og:image" content="{{ og_image }}">
    {% endif %}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{ og_title or seo_title }}">
    <meta name="twitter:description" content="{{ og_description or meta_description }}">
    {% if og_image %}
    <meta name="twitter:image" content="{{ og_image }}">
    {% endif %}
    {% block structured_data %}{% endblock %}
"""
    write(OUT / "includes" / "seo.html", seo)

    base = """<!doctype html>
<html class="no-js" lang="zxx">
<head>
    <meta charset="utf-8">
    <meta http-equiv="x-ua-compatible" content="ie=edge">
    {% include 'includes/seo.html' %}
    {% include 'includes/head.html' %}
</head>
<body>
    <!--[if lte IE 9]>
    	<p class="browserupgrade">You are using an <strong>outdated</strong> browser. Please <a href="https://browsehappy.com/">upgrade your browser</a> to improve your experience and security.</p>
    <![endif]-->
    {% include 'includes/navbar.html' %}
    {% block content %}{% endblock %}
    {% include 'includes/footer.html' %}
    {% include 'includes/scripts.html' %}
</body>
</html>
"""
    write(OUT / "base.html", base)

    pages = {
        "main/home.html": (home_body, True),
    }
    inner_pages = {
        "main/about.html": "about.html",
        "main/contact.html": "contact.html",
        "main/careers.html": "careers.html",
        "main/privacy_policy.html": "privacy-policy.html",
        "main/terms_of_service.html": "terms-of-service.html",
        "main/cookie_policy.html": "cookie-policy.html",
        "main/error.html": "error.html",
    }
    for dest, name in inner_pages.items():
        _, body, _, _ = split_document((SRC / name).read_text(encoding="utf-8"))
        pages[dest] = (body, False)

    index_lines = index.splitlines(keepends=True)
    solutions = "".join(index_lines[397:479])
    services = "".join(index_lines[481:580])
    industries = "".join(index_lines[986:1040])

    def breadcumb(title, bg="img/bg/breadcumb-bg.jpg"):
        return f"""    <div class="breadcumb-wrapper " data-bg-src="{{{{ url_for('static', filename='{bg}') }}}}">
        <div class="container">
            <div class="breadcumb-content">
                <h1 class="breadcumb-title text-anime-style-3">{title}</h1>
                <ul class="breadcumb-menu wow fadeInUp">
                    <li><a href="{{{{ url_for('main.index') }}}}">Home</a></li>
                    <li>{title}</li>
                </ul>
            </div>
        </div>
    </div>
"""

    pages["main/solutions.html"] = (breadcumb("Solutions") + rewrite(solutions), False)
    pages["main/services.html"] = (breadcumb("Services") + rewrite(services), False)
    pages["main/industries.html"] = (breadcumb("Industries") + rewrite(industries), False)

    for dest, (body, _home) in pages.items():
        content = rewrite(body) if dest not in {"main/solutions.html", "main/services.html", "main/industries.html"} else body
        if dest == "main/contact.html":
            content = content.replace(
                '<form action="{{ url_for(\'contact.submit\') }}" method="POST" class="contact-form ajax-contact">',
                '<form action="{{ url_for(\'contact.submit\') }}" method="POST" class="contact-form ajax-contact">\n'
                '                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">\n'
                '                            <input type="text" name="company_website" value="" autocomplete="off" tabindex="-1" style="position:absolute;left:-9999px;height:0;width:0;opacity:0;" aria-hidden="true">',
            )
        wrapped = "{% extends 'base.html' %}\n{% block content %}\n" + content.strip() + "\n{% endblock %}\n"
        write(OUT / dest, wrapped)

    print("templates ready")


if __name__ == "__main__":
    main()
