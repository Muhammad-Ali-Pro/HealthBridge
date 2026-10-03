"""Application shell: role-specific navigation, sidebar, top header and the simulated identity.

DEMO MODE — authentication is simulated. The acting context is (user, organization): a doctor
who works at several organizations chooses which one they are working at, and consent is checked
against exactly that provider + organization.
"""

import base64
from dataclasses import dataclass

import streamlit as st

from core.config import ASSETS_DIR
from core.db import get_session, init_db
from core.models import Role
from core.schemas import Actor
from data.seed import seed_if_empty
from services import demo_service, user_service
from ui.components import ORG_STYLE, avatar_html, badge_html, esc, html, icon, org_badge_html

LOGO_MARK = ASSETS_DIR / "logo_mark.png"
DEMO_LABEL = "DEMO MODE — Authentication simulated"

ROLE_LABELS = {Role.PATIENT: "Patient", Role.DOCTOR: "Doctor", Role.PHARMACIST: "Pharmacy", Role.LAB: "Laboratory"}
ROLE_TONES = {Role.PATIENT: "navy", Role.DOCTOR: "teal", Role.PHARMACIST: "amber", Role.LAB: "blue"}
ROLE_ICONS = {Role.PATIENT: "person", Role.DOCTOR: "stethoscope", Role.PHARMACIST: "local_pharmacy", Role.LAB: "biotech"}


@dataclass(frozen=True)
class Persona:
    role: str
    user_name: str
    organization_name: str | None
    card_title: str        # what the landing card calls this persona
    card_subtitle: str


# The four demo entry points (landing page cards and ?as= deep links).
PERSONAS: dict[str, Persona] = {
    Role.PATIENT: Persona(Role.PATIENT, "Ahmed Khan", None, "Ahmed Khan", "Patient · Karachi"),
    Role.DOCTOR: Persona(Role.DOCTOR, "Dr. Arif Hassan", "South City Hospital", "Dr. Arif",
                         "Cardiologist · South City Hospital & Clifton Medical Centre"),
    Role.PHARMACIST: Persona(Role.PHARMACIST, "Sana Iqbal", "HealthPlus Pharmacy", "HealthPlus Pharmacy",
                             "Sana Iqbal, Pharmacist in charge"),
    Role.LAB: Persona(Role.LAB, "Nadia Farooq", "HealthLab Diagnostics", "HealthLab Diagnostics",
                      "Nadia Farooq, Laboratory Scientist"),
}


@dataclass(frozen=True)
class NavItem:
    path: str
    label: str
    icon: str
    section: str


NAV: dict[str, list[NavItem]] = {
    Role.PATIENT: [
        NavItem("views/patient/home.py", "Home", "home", "My HealthBridge"),
        NavItem("views/patient/my_health.py", "My Health", "favorite", "My HealthBridge"),
        NavItem("views/patient/timeline.py", "Medical Timeline", "timeline", "My HealthBridge"),
        NavItem("views/patient/prescriptions.py", "Prescriptions", "prescriptions", "My HealthBridge"),
        NavItem("views/patient/medications.py", "Medications", "medication", "My HealthBridge"),
        NavItem("views/patient/reports.py", "Lab Reports", "lab_profile", "My HealthBridge"),
        NavItem("views/patient/care_network.py", "Care Network", "diversity_3", "Sharing & privacy"),
        NavItem("views/patient/consent.py", "Consent & Access", "shield_person", "Sharing & privacy"),
    ],
    Role.DOCTOR: [
        NavItem("views/doctor/dashboard.py", "Dashboard", "space_dashboard", "Clinical"),
        NavItem("views/doctor/patients.py", "Patients", "group", "Clinical"),
        NavItem("views/doctor/consultations.py", "Consultations", "stethoscope", "Clinical"),
        NavItem("views/doctor/prescriptions.py", "Prescriptions", "prescriptions", "Clinical"),
        NavItem("views/doctor/timeline.py", "Medical Timeline", "timeline", "Clinical"),
        NavItem("views/doctor/reports.py", "Reports & Documents", "lab_profile", "Clinical"),
        NavItem("views/doctor/organizations.py", "My Organizations", "domain", "Workspace"),
        NavItem("views/doctor/ai_insights.py", "AI Insights", "auto_awesome", "Workspace"),
    ],
    Role.PHARMACIST: [
        NavItem("views/pharmacy/dashboard.py", "Dashboard", "space_dashboard", "Pharmacy"),
        NavItem("views/pharmacy/prescriptions.py", "Prescriptions", "prescriptions", "Pharmacy"),
        NavItem("views/pharmacy/pending.py", "Pending Verification", "fact_check", "Pharmacy"),
        NavItem("views/pharmacy/dispensing.py", "Dispensing", "local_pharmacy", "Pharmacy"),
        NavItem("views/pharmacy/billing.py", "Billing", "receipt_long", "Pharmacy"),
        NavItem("views/pharmacy/patients.py", "Patients", "group", "Pharmacy"),
    ],
    Role.LAB: [
        NavItem("views/lab/dashboard.py", "Dashboard", "space_dashboard", "Laboratory"),
        NavItem("views/lab/orders.py", "Test Orders", "inbox", "Laboratory"),
        NavItem("views/lab/pending.py", "Pending Reports", "pending_actions", "Laboratory"),
        NavItem("views/lab/published.py", "Published Reports", "lab_profile", "Laboratory"),
        NavItem("views/lab/patients.py", "Patients", "group", "Laboratory"),
    ],
}


# ---------------------------------------------------------------------------
# Bootstrap and identity
# ---------------------------------------------------------------------------


@st.cache_resource
def bootstrap_db() -> bool:
    init_db()
    with get_session() as session:
        seed_if_empty(session)
    return True


@st.cache_data(show_spinner=False)
def logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO_MARK.read_bytes()).decode()


def avatar(name: str, size: int = 56) -> str:
    return avatar_html(name, size)


def _clear_selections() -> None:
    for k in [k for k in st.session_state if k.startswith("sel_")]:
        del st.session_state[k]


def enter_as(role: str, go_home: bool = True) -> None:
    """Sign in (simulated) as the demo persona for `role`."""
    ss = st.session_state
    persona = PERSONAS[Role(role)]
    with get_session() as session:
        user_id, org_id = user_service.find_persona(session, persona.user_name, persona.organization_name)
    ss["hb_role"], ss["hb_user_id"], ss["hb_org_id"] = Role(role), user_id, org_id
    ss["hb_entered"] = True
    for k in ("_role_ctl", "_user_ctl", "_org_ctl"):
        ss.pop(k, None)
    _clear_selections()
    ss["_goto_home"] = go_home


def exit_demo() -> None:
    st.session_state["hb_entered"] = False
    _clear_selections()


def handle_deep_link() -> None:
    """?as=patient|doctor|pharmacist|lab enters the demo directly (applied once)."""
    requested = st.query_params.get("as")
    if requested:
        if requested in {r.value for r in Role}:
            enter_as(requested, go_home=False)  # stay on the requested page
        del st.query_params["as"]


def has_entered() -> bool:
    return bool(st.session_state.get("hb_entered"))


def resolve_actor() -> Actor:
    """Resolve the simulated signed-in user and organization context from session state."""
    ss = st.session_state
    ss.setdefault("hb_role", Role.DOCTOR)
    with get_session() as session:
        users = user_service.list_users_by_role(session, ss["hb_role"])
        if ss.get("hb_user_id") not in {u.id for u in users}:
            ss["hb_user_id"], ss["hb_org_id"] = users[0].id, None
        actor = user_service.make_actor(session, ss["hb_user_id"], ss.get("hb_org_id"))
        ss["hb_memberships"] = user_service.memberships(session, actor.id) if actor.role != Role.PATIENT else []
        ss["hb_role_users"] = [
            (u, (user_service.memberships(session, u.id) or [None])[0]) for u in users
        ]
    ss["hb_org_id"] = actor.organization_id
    ss["hb_actor"] = actor
    return actor


def current_actor() -> Actor:
    return st.session_state["hb_actor"]


def _on_role_change() -> None:
    enter_as(st.session_state["_role_ctl"])


def _on_user_change() -> None:
    ss = st.session_state
    ss["hb_user_id"], ss["hb_org_id"] = ss["_user_ctl"], None
    ss.pop("_org_ctl", None)
    _clear_selections()


def _on_org_change() -> None:
    st.session_state["hb_org_id"] = st.session_state["_org_ctl"]
    _clear_selections()


def _reset_demo() -> None:
    demo_service.reset_demo_data()
    _clear_selections()
    st.session_state["hb_flash"] = "Demo data restored to its original state."


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


# Workflow pages reachable from buttons (not listed in the sidebar). title → parent nav label.
HIDDEN_PAGES: dict[str, list[tuple[str, str, str]]] = {
    Role.DOCTOR: [
        ("views/doctor/consultation_editor.py", "Consultation form", "Consultations"),
        ("views/doctor/consultation_detail.py", "Consultation details", "Consultations"),
        ("views/doctor/prescription_editor.py", "Prescription form", "Prescriptions"),
        ("views/doctor/prescription_detail.py", "Prescription details", "Prescriptions"),
    ],
}


def nav_items(actor: Actor) -> list[NavItem]:
    return NAV[actor.role]


def home_path(actor: Actor) -> str:
    return NAV[actor.role][0].path


def active_nav_label(actor: Actor, page_title: str) -> str:
    for _, title, parent in HIDDEN_PAGES.get(actor.role, []):
        if title == page_title:
            return parent
    return page_title


def build_navigation(actor: Actor):
    pages = [st.Page(n.path, title=n.label, icon=f":material/{n.icon}:", default=i == 0)
             for i, n in enumerate(nav_items(actor))]
    pages += [st.Page(path, title=title, visibility="hidden") for path, title, _ in HIDDEN_PAGES.get(actor.role, [])]
    page = st.navigation(pages, position="hidden")
    if st.session_state.pop("_goto_home", False) and page.title != nav_items(actor)[0].label:
        st.switch_page(home_path(actor))
    return page


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def context_label(actor: Actor) -> str:
    return actor.organization.name if actor.organization else "My HealthBridge"


def render_sidebar(page, actor: Actor) -> None:
    with st.sidebar, st.container(key="hb_sidebar"):
        html(f'<div class="hb-brand"><img src="{logo_data_uri()}" alt="HealthBridge"/>'
             f'<div><span class="wordmark">Health<span>Bridge</span></span>'
             f'<div class="hb-brand-tag">One patient · one timeline</div></div></div>')
        with st.container(key="hb_back_home"):
            st.button("Back to home page", icon=":material/arrow_back:", on_click=exit_demo, key="sb_home",
                      type="tertiary", help="Leave the demo workspace and return to the HealthBridge home page")

        section = None
        active = active_nav_label(actor, page.title)
        for item in nav_items(actor):
            if item.section != section:
                section = item.section
                html(f'<div class="hb-nav-label">{esc(section)}</div>')
            if item.label == active:
                html(f'<div class="hb-nav-active">{icon(item.icon, 20, fill=True)}<span>{esc(item.label)}</span></div>')
            else:
                st.page_link(item.path, label=item.label, icon=f":material/{item.icon}:", width="stretch")

        with st.container(key="hb_sidebar_profile"):
            html(f"""
              <div class="hb-profile">{avatar_html(actor.user.name, 36)}
                <div class="who"><div class="name">{esc(actor.user.name)}</div>
                  <div class="meta">{esc(ROLE_LABELS[actor.role])} · {esc(context_label(actor))}</div></div>
              </div>
              <div class="hb-demo">{icon("science", 14)}{esc(DEMO_LABEL)}</div>""")


# ---------------------------------------------------------------------------
# Top header
# ---------------------------------------------------------------------------


def render_topbar(page, actor: Actor) -> None:
    with st.container(key="hb_topbar"):
        left, mid, right = st.columns([4, 3, 4], vertical_alignment="center")
        with left:
            ctx = (org_badge_html(actor.organization.name, actor.organization.org_type) if actor.organization
                   else f"<span>{icon('person', 16)} My HealthBridge</span>")
            html(f"""<div class="hb-crumbs">{icon("home", 16)}<span>HealthBridge</span><span class="sep">/</span>
                  {ctx}<span class="sep">/</span><span class="current">{esc(page.title)}</span></div>""")
        with mid:
            if actor.role == Role.DOCTOR:
                _header_search(page)
        with right, st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
            st.button("Home page", icon=":material/home:", on_click=exit_demo, key="tb_home", type="tertiary",
                      help="Return to the HealthBridge home page to pick another demo role")
            html(badge_html(ROLE_LABELS[actor.role], ROLE_TONES[actor.role], ROLE_ICONS[actor.role]), width="content")
            _profile_menu(actor)

    flash = st.session_state.pop("hb_flash", None)
    if flash:
        st.toast(flash, icon=":material/check_circle:")


def _header_search(page) -> None:
    query = st.text_input("Search patients", key="hb_search", placeholder="Find a patient by name or HB-ID",
                          label_visibility="collapsed", icon=":material/search:")
    ss = st.session_state
    if query != ss.get("_last_search", ""):
        ss["_last_search"] = query
        ss.pop("sel_patient", None)
        if query and page.title != "Patients":
            st.switch_page("views/doctor/patients.py")


def _profile_menu(actor: Actor) -> None:
    ss = st.session_state
    with st.popover(actor.user.name, icon=":material/account_circle:"):
        html(f"""
          <div class="hb-patient" style="align-items:center;margin-bottom:.75rem">{avatar_html(actor.user.name, 44)}
            <div><div class="name">{esc(actor.user.name)}</div>
              <div class="meta" style="margin:0">{esc(ROLE_LABELS[actor.role])} · {esc(context_label(actor))}</div></div>
          </div>
          <div class="hb-demo" style="margin:0 0 .9rem">{icon("science", 14)}{esc(DEMO_LABEL)}</div>""")

        st.segmented_control("View as", list(ROLE_LABELS), default=ss["hb_role"], required=True, key="_role_ctl",
                             format_func=lambda r: ROLE_LABELS[r], on_change=_on_role_change, width="stretch")
        options = ss["hb_role_users"]
        ids = [u.id for u, _ in options]
        names = {u.id: u.name for u, _ in options}
        st.radio("Signed in as", ids, index=ids.index(ss["hb_user_id"]), key="_user_ctl",
                 format_func=names.__getitem__, on_change=_on_user_change,
                 captions=[m.organization.name if m else "Patient account" for _, m in options])

        memberships = ss["hb_memberships"]
        if len(memberships) > 1:
            org_ids = [m.organization.id for m in memberships]
            labels = {m.organization.id: f"{m.organization.name}" for m in memberships}
            st.radio("Working at", org_ids, index=org_ids.index(actor.organization_id), key="_org_ctl",
                     format_func=labels.__getitem__, on_change=_on_org_change,
                     captions=[f"{ORG_STYLE[m.organization.org_type][0]} · {m.title}" for m in memberships],
                     help="Patient consent is specific to you AND the organization you are working at.")
        st.divider()
        st.button("Reset demo data", icon=":material/restart_alt:", on_click=_reset_demo, width="stretch",
                  help="Restore the synthetic demo data (undoes consent changes).")
        st.button("Exit to home page", icon=":material/logout:", on_click=exit_demo, width="stretch")
        st.caption("Identity switching is simulated for the demo. No passwords or real accounts.")
