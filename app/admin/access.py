from app.extensions import db
from app.models import StaffRole

PERMISSIONS = (
    ("overview", "Overview", "Dashboard"),
    ("crm.view", "View leads", "Leads"),
    ("crm.edit", "Update leads", "Leads"),
    ("leads.export", "Export leads", "Leads"),
    ("content.view", "View content", "Content"),
    ("content.edit", "Edit content", "Content"),
    ("content.publish", "Publish content", "Content"),
    ("careers.view", "View careers", "Careers"),
    ("careers.edit", "Edit careers", "Careers"),
    ("seo.manage", "Manage SEO", "Marketing"),
    ("media.manage", "Manage media", "Content"),
    ("settings.manage", "Configure website", "Website"),
    ("audit.view", "View audit logs", "Governance"),
    ("users.manage", "Manage users", "Administration"),
    ("roles.manage", "Manage roles", "Administration"),
)

ALL_CODES = tuple(code for code, _label, _group in PERMISSIONS)

DEFAULT_ROLES = (
    ("administrator", "Administrator", ALL_CODES, True),
    ("website", "Website Administrator", ("overview", "content.view", "content.edit", "content.publish", "settings.manage", "media.manage", "seo.manage"), False),
    ("content", "Content Manager", ("overview", "content.view", "content.edit", "content.publish", "media.manage"), False),
    ("author", "Author", ("overview", "content.view", "content.edit"), False),
    ("reviewer", "Reviewer", ("overview", "content.view", "content.publish"), False),
    ("marketing", "Marketing", ("overview", "crm.view", "seo.manage", "content.view", "leads.export"), False),
    ("sales", "Sales", ("overview", "crm.view", "crm.edit", "leads.export"), False),
    ("hr", "HR", ("overview", "careers.view", "careers.edit"), False),
    ("crm", "CRM", ("overview", "crm.view", "crm.edit"), False),
    ("editor", "Editor", ("overview", "content.view", "content.edit", "content.publish", "careers.view", "careers.edit"), False),
    ("viewer", "Viewer", ("overview", "crm.view", "content.view", "careers.view"), False),
)


def ensure_roles():
    admin = StaffRole.query.filter_by(slug="administrator").first()
    if admin and admin.permissions == ",".join(ALL_CODES) and StaffRole.query.count() >= len(DEFAULT_ROLES):
        return
    for slug, name, codes, system in DEFAULT_ROLES:
        role = StaffRole.query.filter_by(slug=slug).first()
        if role is None:
            db.session.add(
                StaffRole(slug=slug, name=name, permissions=",".join(codes), is_system=system)
            )
        elif slug == "administrator":
            role.permissions = ",".join(ALL_CODES)
            role.is_system = True
            role.name = name
    db.session.commit()


def ensure_staff_role(staff):
    ensure_roles()
    if staff.role_id is None:
        staff.role = StaffRole.query.filter_by(slug="administrator").one()
        db.session.commit()
