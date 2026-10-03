import streamlit as st

from core.db import get_session
from core.models import RecordCategory
from services import patient_service, record_service
from ui import doctor
from ui.components import (
    badge_html,
    card,
    consultation_list_html,
    document_card_html,
    empty_state,
    esc,
    html,
    icon,
    page_header,
    patient_entry_html,
    prescription_card_html,
    section_header,
    timeline,
)
from ui.sections import consultation_card, medications_html, notes_card, patient_hero, timeline_with_filters
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state
DOCTOR_FILTERS = ["All", "Consultations", "Prescriptions", "Documents", "Medications"]


def _close() -> None:
    ss.pop("sel_patient", None)


def directory() -> None:
    page_header("Patients", f"Search the HealthBridge directory. Records open only when the patient has granted you "
                f"access at {actor.organization.name}.", eyebrow="Patients")
    with card("pt_search"):
        q = st.text_input("Search patients", key="pt_q", value=ss.get("hb_search", ""), icon=":material/person_search:",
                          placeholder="Name, HealthBridge ID (HB-000001) or phone number", label_visibility="collapsed")
        st.caption("Search results show identity only — never medical information.")
    with get_session() as s:
        entries = patient_service.directory(s, actor, q)
    entries = sorted(entries, key=lambda e: not e.access.allowed)
    if not entries:
        empty_state("No matching patients", "Try a name, an HB-ID such as HB-000001, or a phone number.", "person_search")
        return
    section_header("Results", f"{len(entries)} patient{'s' if len(entries) != 1 else ''}")
    cols = st.columns(3)
    for i, e in enumerate(entries):
        p = e.patient
        status = (badge_html("Access granted", "teal", "verified_user") if e.access.allowed
                  else badge_html("Access restricted", "neutral", "lock"))
        with cols[i % 3], card(f"pt_{p.id}"):
            html(f"""<div class="hb-patient"><span class="hb-avatar" style="width:44px;height:44px;font-size:17px">{esc(''.join(w[0] for w in p.name.split()[:2]))}</span>
                 <div class="body"><div class="name">{esc(p.name)}</div><div class="meta" style="margin-bottom:.4rem">{esc(p.display_id)}</div>
                 <div style="font-size:.84rem;color:var(--hb-navy-600)">{p.age} years · {esc(p.sex.title())}</div></div></div>
                 <div style="margin-top:.7rem">{status}</div>""")
            if st.button("Open Patient", key=f"open_{p.id}", icon=":material/folder_open:", width="stretch",
                         type="primary" if e.access.allowed else "secondary"):
                doctor.open_patient(p.id)


def profile(entry) -> None:
    p = entry.patient
    st.button("All patients", icon=":material/arrow_back:", on_click=_close, type="tertiary")
    page_header("Patient profile", f"Working at {actor.organization.name}", eyebrow="Patients")
    doctor.patient_header(p)
    doctor.consent_banner(actor, entry.access, p.name)
    if not entry.access.allowed:
        return

    with get_session() as s:
        record = record_service.get_authorized_record(s, actor, p.id, view="patient_record")
    access = record.access

    with st.container(horizontal=True, gap="small"):
        if st.button("New consultation", icon=":material/add:", type="primary"):
            doctor.new_consultation(p.id)
        if st.button("Create prescription", icon=":material/prescriptions:"):
            doctor.new_prescription(p.id)
        if st.button("Generate Clinical Summary", icon=":material/auto_awesome:"):
            doctor.generate_summary(p.id)

    t_over, t_tl, t_cons, t_rx, t_docs = st.tabs(["Overview", "Timeline", "Consultations", "Prescriptions", "Documents"])
    clinical_ok = access.can(RecordCategory.CONSULTATIONS) or access.can(RecordCategory.HOSPITAL_RECORDS)

    with t_over:
        patient_hero(record, right_badge=badge_html("Authorized view", "teal", "verified_user"))
        left, right = st.columns([3, 2], gap="large")
        with left:
            section_header("Recent authorized activity")
            with st.container(key="hbcard_over_tl"):
                timeline(record.timeline[:5], empty_body="No records in the categories shared with you.")
        with right:
            section_header("Current medications")
            if access.can(RecordCategory.MEDICATIONS):
                html(f'<div class="hb-card">{medications_html([m for m in record.medications if m.current])}</div>')
            else:
                doctor.locked_tab("Current medications")
            section_header("Recent consultations")
            if record.consultations:
                consultation_card(record.consultations[0])
            elif not clinical_ok:
                doctor.locked_tab("Consultations")
            else:
                empty_state("No consultations yet", icon_name="stethoscope")
            section_header("Recent prescriptions")
            if not access.can(RecordCategory.PRESCRIPTIONS):
                doctor.locked_tab("Prescriptions")
            for rx in record.prescriptions[:2]:
                html(f'<div class="hb-card">{prescription_card_html(rx, show_patient=False)}</div>')

    with t_tl:
        timeline_with_filters(record.timeline, key="pt_profile_tl", title="Authorized medical timeline",
                              filters=DOCTOR_FILTERS)

    with t_cons:
        if not clinical_ok:
            doctor.locked_tab("Consultations")
        elif not record.consultations:
            empty_state("No consultations yet", icon_name="stethoscope")
        for c in record.consultations:
            with card(f"cons_{c.id}"):
                html(consultation_list_html(c))
                if st.button("View details", key=f"vc_{c.id}", icon=":material/open_in_new:"):
                    doctor.view_consultation(c.id)
        if record.notes:
            notes_card(record.notes)

    with t_rx:
        if not access.can(RecordCategory.PRESCRIPTIONS):
            doctor.locked_tab("Prescriptions")
        elif not record.prescriptions:
            empty_state("No prescriptions yet", icon_name="prescriptions")
        cols = st.columns(2)
        for i, rx in enumerate(record.prescriptions):
            with cols[i % 2], card(f"rx_{rx.id}"):
                html(prescription_card_html(rx, show_patient=False))
                if st.button("View prescription", key=f"vrx_{rx.id}", icon=":material/open_in_new:"):
                    doctor.view_prescription(rx.id)

    with t_docs:
        if not access.can(RecordCategory.DOCUMENTS):
            doctor.locked_tab("Documents")
        else:
            cols = st.columns(3)
            for i, d in enumerate(record.documents):
                with cols[i % 3]:
                    html(f'<div class="hb-card">{document_card_html(d)}</div>')
            if record.patient_entries:
                section_header("Patient-provided information")
                html('<div class="hb-card" style="padding-top:.4rem">' + "".join(map(patient_entry_html, record.patient_entries)) + "</div>")
            if not record.documents and not record.patient_entries:
                empty_state("No documents yet", icon_name="description")
    html(f'<div style="font-size:.76rem;color:var(--hb-muted);margin-top:.6rem">{icon("visibility", 14)} '
         f'Opening this record was logged in {esc(p.name)}\'s access history.</div>')


with get_session() as s:
    everyone = {e.patient.id: e for e in patient_service.directory(s, actor)}

selected = everyone.get(ss.get("sel_patient"))
if selected:
    profile(selected)
else:
    directory()
