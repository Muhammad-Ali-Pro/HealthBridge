import streamlit as st

from core.db import get_session
from services import patient_service, record_service
from ui.components import empty_state, html, page_header, patient_card_html, section_header
from ui import doctor
from ui.sections import medications_html, timeline_with_filters
from ui.shell import current_actor

actor = current_actor()
org_name = actor.organization.name
ss = st.session_state

with get_session() as s:
    shared = patient_service.with_access(s, actor)

head, picker = st.columns([2, 1], vertical_alignment="bottom")
with head:
    page_header("Medical Timeline", "One longitudinal record across every provider — limited to what each patient shared with you.",
                eyebrow="Clinical")

if not shared:
    empty_state("No patients have shared records with you here",
                f"Patients grant access to you at {org_name}. Use the “Working at” switcher in the top bar to change organization.", "lock")
else:
    ids = [e.patient.id for e in shared]
    with picker:
        pid = st.selectbox("Patient", ids, index=ids.index(ss["sel_patient"]) if ss.get("sel_patient") in ids else 0,
                           format_func={e.patient.id: f"{e.patient.name}  ·  {e.patient.display_id}" for e in shared}.__getitem__)
    ss["sel_patient"] = pid
    with get_session() as s:
        record = record_service.get_authorized_record(s, actor, pid, view="medical_timeline")

    doctor.consent_banner(actor, record.access, record.patient.name)
    st.write("")
    left, right = st.columns([1, 2.2], gap="large")
    with left:
        html(f'<div class="hb-card">{patient_card_html(record.patient)}</div>')
        if record.access.can("medications"):
            section_header("Current medications")
            html(f'<div class="hb-card">{medications_html([m for m in record.medications if m.current])}</div>')
    with right:
        timeline_with_filters(record.timeline, key="dr_tl", title="Timeline", access=record.access)
