import os
from datetime import datetime, timezone

from app.extensions import db
from app.models import Article, CaseStudy, Category, PageSeo

PUBLISHED = datetime(2025, 1, 15, tzinfo=timezone.utc)
CONTENT_DIR = os.path.join(os.path.dirname(__file__), "content")


def seed():
    categories = {
        "Security": _category("Security", "security"),
        "Generative AI": _category("Generative AI", "generative-ai"),
        "AI Agents": _category("AI Agents", "ai-agents"),
        "Enterprise RAG": _category("Enterprise RAG", "enterprise-rag"),
        "AI Security": _category("AI Security", "ai-security"),
        "Machine Learning": _category("Machine Learning", "machine-learning"),
        "Integration": _category("Integration", "integration"),
    }
    articles = [
        dict(
            title="RatHat Android Trojan Uses AI for Automation",
            slug="rathat-android-trojan-uses-ai-for-automation",
            excerpt="RatHat is an Android trojan that uses generative AI to navigate infected devices in real time. Zimperium's report shows why mobile threats are shifting from fixed scripts to adaptive automation, and what enterprises should change in response.",
            content=(
                "<p>A newly discovered Android trojan relies on generative AI to more intelligently navigate and control infected devices, mobile security company Zimperium reports.</p>"
                "<p>Dubbed RatHat, the malware has been distributed through smishing and malvertising, relying on an automated multi-stage infection pipeline to break out of Android’s application sandbox and gain shell-level execution.</p>"
                "<p>RatHat contains typical mobile malware capabilities: it steals users’ credentials, mimics banking and payment applications, and establishes a covert communication channel with its command-and-control server.</p>"
                "<p>Unlike other mobile threats, it also uses generative AI to navigate and control the device interface in real time, and monitors input at the hardware level to reconstruct PIN codes, passwords, and patterns.</p>"
            ),
            category="Security",
            featured_image="img/blog/rathat-blog.jpg",
            published_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
            featured=True,
        ),
        dict(
            title="Building Production-Ready Generative AI for the Enterprise",
            slug="building-production-ready-generative-ai-for-the-enterprise",
            excerpt="A generative AI demo is not a production system. Enterprise teams need grounding, evaluation, security, and an operating model before a copilot touches real data and workflows.",
            content="<p>Production generative AI has to work with enterprise data, applications, security controls, and the way teams already operate. Neural Xpert designs those systems so they can be deployed, monitored, and improved after the pilot.</p>",
            category="Generative AI",
            featured_image="img/blog/generative-ai-blog.jpg",
            published_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
        ),
        dict(
            title="Designing AI Agents That Run Enterprise Workflows",
            slug="designing-ai-agents-that-run-enterprise-workflows",
            excerpt="An AI agent is useful when it can complete a multi-step workflow across systems such as Microsoft 365, SAP, or Salesforce and still leave people in control of the decisions that matter.",
            content="<p>Enterprise AI agents are useful when they can take a multi-step workflow across business systems and still leave people in control of the decisions that matter.</p>",
            category="AI Agents",
            featured_image="img/blog/ai-agents-blog.jpg",
            published_at=datetime(2025, 1, 19, tzinfo=timezone.utc),
        ),
        dict(
            title="Connecting Enterprise Knowledge with Secure RAG",
            slug="connecting-enterprise-knowledge-with-secure-rag",
            excerpt="Retrieval-augmented generation is only as trustworthy as the knowledge it can reach. Secure RAG keeps answers grounded in documents and data the organization is allowed to use.",
            content="<p>Secure RAG connects documents, databases, and internal knowledge to answers that stay grounded in sources the organization already trusts.</p>",
            category="Enterprise RAG",
            featured_image="img/blog/secure-rag-blog.jpg",
            published_at=datetime(2025, 1, 20, tzinfo=timezone.utc),
        ),
        dict(
            title="Securing AI Systems from Design Through Production",
            slug="securing-ai-systems-from-design-through-production",
            excerpt="A model that works in a demo still needs security once it reaches production. AI security has to cover design, data, prompts, tools, deployment, and monitoring.",
            content="<p>AI security has to cover design, testing, deployment, and monitoring. A model that works in a demo still needs governance once it reaches production.</p>",
            category="AI Security",
            featured_image="img/blog/ai-security-blog.jpg",
            published_at=datetime(2025, 1, 22, tzinfo=timezone.utc),
        ),
        dict(
            title="Moving Machine Learning from Pilots into Operations",
            slug="moving-machine-learning-from-pilots-into-operations",
            excerpt="Machine learning pilots are relatively easy to demonstrate. Turning them into reliable systems that continuously support real business operations is much harder.",
            content="",
            category="Machine Learning",
            featured_image="img/blog/mlops-blog.jpg",
            published_at=datetime(2026, 9, 28, tzinfo=timezone.utc),
        ),
        dict(
            title="Integrating AI with Enterprise Applications and Data",
            slug="integrating-ai-with-enterprise-applications-and-data",
            excerpt="AI creates value when it is connected to the applications and data the business already runs, and when the result can be measured in the workflow it supports.",
            content="<p>AI creates value when it is connected to the applications and data the business already uses, and when the outcome can be measured in the workflow it supports.</p>",
            category="Integration",
            featured_image="img/blog/integration-blog.jpg",
            published_at=datetime(2025, 1, 29, tzinfo=timezone.utc),
        ),
    ]
    for row in articles:
        category = categories[row.pop("category")]
        content_file = os.path.join(CONTENT_DIR, f"{row['slug']}.html")
        if os.path.isfile(content_file):
            with open(content_file, encoding="utf-8") as handle:
                row["content"] = handle.read()
        article = Article.query.filter_by(slug=row["slug"]).first()
        fields = dict(category=category, author="Neural Xpert", status="published", seo_title=row["title"], meta_description=row["excerpt"], **row)
        if article is None:
            db.session.add(Article(**fields))
        elif not article.managed_in_admin:
            for key, value in fields.items():
                setattr(article, key, value)

    if CaseStudy.query.first() is None:
        _seed_case_studies()
    if PageSeo.query.first() is None:
        _seed_pages()
    db.session.commit()


def _seed_case_studies():
    studies = [
        ("Enterprise AI Knowledge Assistant", "enterprise-ai-knowledge-assistant", "Generative AI, Enterprise RAG, Knowledge Intelligence", "Designed an intelligent knowledge solution that enables teams to securely search, retrieve, and interact with information across enterprise documents and internal knowledge sources.", "img/project/knowledge-assistant.jpg", "ENTERPRISE KNOWLEDGE"),
        ("AI-Powered Customer Service Automation", "ai-powered-customer-service-automation", "AI Agents, Generative AI, RAG, Automation", "Built an intelligent customer operations solution combining conversational AI, enterprise knowledge retrieval, workflow automation, and human escalation to improve service delivery.", "img/project/customer-service.jpg", "CUSTOMER OPERATIONS"),
        ("Intelligent Document Processing", "intelligent-document-processing", "Generative AI, Machine Learning, Intelligent Automation", "Developed an AI-powered document processing solution to extract, classify, understand, and route information from complex business documents into existing enterprise workflows.", "img/project/document-processing.jpg", "DOCUMENT INTELLIGENCE"),
        ("AI Agents for Business Process Automation", "ai-agents-for-business-process-automation", "AI Agents, Enterprise Integration, Automation", "Designed intelligent agents that connect with enterprise applications, APIs, and business systems to automate multi-step operational workflows while maintaining human oversight.", "img/project/business-automation.jpg", "ENTERPRISE AUTOMATION"),
        ("Predictive Intelligence Platform", "predictive-intelligence-platform", "Machine Learning, Predictive Analytics, Data Intelligence", "Developed a machine learning solution that transforms operational data into predictive insights for forecasting, anomaly detection, risk analysis, and business decision support.", "img/project/predictive-intelligence.jpg", "DATA & ANALYTICS"),
        ("Production AI Platform", "production-ai-platform", "AI Engineering, MLOps, AI Security, Cloud", "Designed a secure AI platform architecture supporting application integration, model evaluation, observability, governance, deployment, and continuous optimization for enterprise AI workloads.", "img/project/production-ai-platform.jpg", "AI PLATFORM ENGINEERING"),
    ]
    for title, slug, technologies, summary, image, industry in studies:
        db.session.add(
            CaseStudy(
                title=title,
                slug=slug,
                category=technologies.split(",")[0].strip(),
                summary=summary,
                content=f"<p>{summary}</p>",
                technologies=technologies,
                featured_image=image,
                client_display_name="Enterprise client",
                industry=industry,
                status="published",
                published_at=PUBLISHED,
                seo_title=title,
                meta_description=summary,
            )
        )


def _seed_pages():
    pages = {
        "home": ("Neural Xpert | Enterprise AI, Generative AI & AI Solutions", "Neural Xpert builds secure enterprise AI solutions, including Generative AI, AI agents, RAG, machine learning, intelligent automation, AI integration and AI security."),
        "about": ("About Neural Xpert | Enterprise AI", "Neural Xpert is an enterprise technology company focused on Artificial Intelligence, Cloud Engineering, and Cybersecurity."),
        "insights": ("Neural Xpert | Enterprise AI Insights", "Insights on enterprise AI, generative AI, AI agents, RAG, machine learning, and AI security from Neural Xpert."),
        "case-studies": ("Case Studies | Neural Xpert", "Explore how Neural Xpert designs and delivers secure, production-ready AI solutions for the enterprise."),
        "careers": ("Neural Xpert | Careers", "Build enterprise AI with Neural Xpert."),
        "contact": ("Contact Neural Xpert", "Talk with Neural Xpert about an enterprise AI program."),
    }
    for key, (title, description) in pages.items():
        db.session.add(PageSeo(page_key=key, seo_title=title, meta_description=description))
    db.session.commit()


def _category(name, slug):
    category = Category.query.filter_by(slug=slug).first()
    if category is None:
        category = Category(name=name, slug=slug, kind="article")
        db.session.add(category)
    return category
