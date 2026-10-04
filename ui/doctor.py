"""Doctor workflow building blocks: navigation between workflow pages, consent banner, patient header."""

import streamlit as st

from core.db import get_session
from core.models import RecordCategory
from core.schemas import AccessDecision, Actor, PatientIdentity
from services import access_service, patient_service, user_service
from ui.components import CATEGORY_STYLE, avatar_html, badge_html, esc, html, icon, org_badge_html

PATIENTS = "views/doctor/patients.py"
CONSULTATION_EDITOR = "views/doctor/consultation_editor.py"
CONSULTATION_DETAIL = "views/doctor/consultation_detail.py"
PRESCRIPTION_EDITOR = "views/doctor/prescription_editor.py"
PRESCRIPTION_DETAIL = "views/doctor/prescription_detail.py"
AI_INSIGHTS = "views/doctor/ai_insights.py"

ss = st.session_state


# --- Navigation (call from the main script flow, e.g. inside `if st.button(...)`) ---------------

def open_patient(patient_id: int) -> None:
    ss["sel_patient"] = patient_id
    ss["_hb_search_clear"] = True   # the search did its job; don't let it interfere with the open workspace
    st.switch_page(PATIENTS)


VISIT_STATE = ("ce_visit_for", "ce_visit_date", "ce_visit_time", "ce_visit_max")


def reset_visit_time() -> None:
    """Forget the consultation form's visit date/time so the next form starts from 'now' (or the draft's time)."""
    for k in VISIT_STATE:
        ss.pop(k, None)


def new_consultation(patient_id: int | None) -> None:
    if patient_id:
        ss["sel_patient"] = patient_id
    ss.pop("sel_edit_consultation", None)
    ss.pop("consult_errors", None)
    reset_visit_time()
    st.switch_page(CONSULTATION_EDITOR)


def edit_consultation(consultation_id: int, patient_id: int) -> None:
    ss["sel_patient"], ss["sel_edit_consultation"] = patient_id, consultation_id
    ss.pop("consult_errors", None)
    reset_visit_time()
    st.switch_page(CONSULTATION_EDITOR)


def view_consultation(consultation_id: int) -> None:
    ss["sel_consultation"] = consultation_id
    st.switch_page(CONSULTATION_DETAIL)


def new_prescription(patient_id: int | None, consultation_id: int | None = None) -> None:
    if patient_id:
        ss["sel_patient"] = patient_id
    ss["sel_rx_edit"] = None
    ss["sel_rx_consultation"] = consultation_id
    ss.pop("rx_rows", None)
    st.switch_page(PRESCRIPTION_EDITOR)


def edit_prescription(prescription_id: int, patient_id: int) -> None:
    ss["sel_patient"], ss["sel_rx_edit"] = patient_id, prescription_id
    ss.pop("rx_rows", None)
    st.switch_page(PRESCRIPTION_EDITOR)


def view_prescription(prescription_id: int) -> None:
    ss["sel_rx"] = prescription_id
    st.switch_page(PRESCRIPTION_DETAIL)


def generate_summary(patient_id: int) -> None:
    ss["sel_patient"], ss["copilot_autorun"] = patient_id, True
    st.switch_page(AI_INSIGHTS)


# --- Display ------------------------------------------------------------------------------------

def patient_header(p: PatientIdentity, right: str = "") -> None:
    html(f"""<div class="hb-card"><div class="hb-hero">{avatar_html(p.name, 60)}
      <div style="flex:1;min-width:220px"><div class="name">{esc(p.name)}</div>
        <div class="meta"><span>{icon("badge", 16)} {esc(p.display_id)}</span>
          <span>{icon("cake", 16)} {p.age} years</span><span>{icon("person", 16)} {esc(p.sex.title())}</span></div></div>
      <div>{right}</div></div></div>""")


def consent_banner(actor: Actor, decision: AccessDecision, patient_name: str) -> None:
    """Spec'd consent status: provider + organization + ✓ granted / 🔒 locked categories."""
    org = actor.organization
    who = (f'<div class="hb-kv" style="margin-top:.6rem"><span class="k">Provider</span><span class="v">{esc(actor.user.name)}</span>'
           f'<span class="k">Organization</span><span class="v">{org_badge_html(org.name, org.org_type)}</span></div>')
    if decision.allowed:
        cats = []
        for c in RecordCategory:
            label = CATEGORY_STYLE[c.value][0]
            cats.append(badge_html(label, "teal", "check_circle") if decision.can(c.value)
                        else badge_html(label, "neutral", "lock"))
        html(f"""<div class="hb-access ok" style="display:block">
          <div style="display:flex;gap:.6rem;align-items:center">{icon("verified_user", 20, fill=True)}
            <div class="t" style="font-size:.98rem">Patient has granted you access</div></div>{who}
          <div style="margin-top:.7rem;display:flex;gap:.35rem;flex-wrap:wrap">{''.join(cats)}</div></div>""")
        return
    elsewhere = _access_elsewhere(actor, decision.patient_id)
    hint = (f'<div class="s" style="margin-top:.6rem">{icon("info", 14)} You do have access when working at '
            f'<b>{esc(", ".join(elsewhere))}</b> — switch organization using the “Working at” selector in the top bar.</div>' if elsewhere else "")
    html(f"""<div class="hb-access locked" style="display:block;border-color:#E3C9C2;background:#FBF4F2">
      <div style="display:flex;gap:.6rem;align-items:center;color:#8A2E20">{icon("lock", 20, fill=True)}
        <div class="t" style="font-size:1rem;color:#8A2E20;letter-spacing:.04em">ACCESS RESTRICTED</div></div>
      <div style="font-size:.92rem;color:var(--hb-navy);margin-top:.5rem">{esc(patient_name)} has not granted you access to these records.</div>
      <div class="s">Ask the patient to grant access through HealthBridge (Consent &amp; Access). Consent is specific to you
        <b>and</b> the organization you are working at.</div>{who}{hint}</div>""")


def _access_elsewhere(actor: Actor, patient_id: int) -> list[str]:
    """Organizations where THIS doctor has their own active consent for the patient (their own information)."""
    names = []
    with get_session() as s:
        for m in user_service.memberships(s, actor.id):
            if m.organization.id == actor.organization_id:
                continue
            other = user_service.make_actor(s, actor.id, m.organization.id)
            if access_service.authorize(s, other, patient_id).allowed:
                names.append(m.organization.name)
    return names


def locked_tab(category_label: str) -> None:
    html(f"""<div class="hb-alert lock">{icon("lock", 20, fill=True)}<div><div class="t">{esc(category_label)} not shared with you</div>
         <div class="b">The patient has not included this category in your consent at this organization.</div></div></div>""")


def pick_patient(actor: Actor, key: str, label: str = "Patient") -> int | None:
    """Patient selector limited to patients who have granted this doctor access here."""
    with get_session() as s:
        entries = patient_service.with_access(s, actor)
    if not entries:
        html(f'<div class="hb-alert lock">{icon("lock", 20, fill=True)}<div><div class="t">No patients have shared records with you here</div>'
             f'<div class="b">Records — and new clinical records — require patient consent for you at {esc(actor.organization.name)}.</div></div></div>')
        return None
    ids = [e.patient.id for e in entries]
    current = ss.get("sel_patient")
    pid = st.selectbox(label, ids, index=ids.index(current) if current in ids else None, key=key,
                       placeholder="Choose a patient who has granted you access",
                       format_func={e.patient.id: f"{e.patient.name}  ·  {e.patient.display_id}" for e in entries}.__getitem__)
    if pid:
        ss["sel_patient"] = pid
    return pid


def show_errors(errors: dict[str, str], field: str) -> None:
    if field in errors:
        st.markdown(f'<div class="hb-field-error">{icon("error", 14)} {esc(errors[field])}</div>', unsafe_allow_html=True)
