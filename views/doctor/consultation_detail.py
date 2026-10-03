import streamlit as st

from core.db import get_session
from core.models import DocumentType, NoteType
from services import clinical_service, document_service
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError
from ui import doctor
from ui.components import (
    badge_html,
    card,
    document_card_html,
    empty_state,
    esc,
    fmt_datetime,
    html,
    icon,
    org_badge_html,
    page_header,
    section_header,
    verified_badge_html,
)
from ui.sections import notes_list_html
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state
cid = ss.get("sel_consultation")

NOTE_TYPES = {NoteType.CONSULTATION: "Consultation note", NoteType.FOLLOW_UP: "Follow-up note",
              NoteType.OBSERVATION: "Clinical observation", NoteType.INTERNAL: "Internal clinical note"}
DOC_TYPES = {DocumentType.MEDICAL_REPORT: "Medical report", DocumentType.REFERRAL_LETTER: "Referral letter",
             DocumentType.IMAGING_REPORT: "Imaging report", DocumentType.LAB_REPORT: "External lab report",
             DocumentType.DISCHARGE_SUMMARY: "Discharge summary", DocumentType.OTHER: "Other"}

if st.button("Back to patient", icon=":material/arrow_back:", type="tertiary"):
    st.switch_page(doctor.PATIENTS)

try:
    with get_session() as s:
        c = clinical_service.get_consultation(s, actor, cid) if cid else None
        notes = clinical_service.notes_for_consultation(s, actor, cid) if c else []
        docs = document_service.for_consultation(s, actor, cid) if c else []
except AccessDenied as exc:
    page_header("Consultation", eyebrow="Consultations")
    doctor.locked_tab(f"This consultation ({exc})")
    st.stop()

if c is None:
    page_header("Consultation", eyebrow="Consultations")
    empty_state("No consultation selected", "Open a consultation from a patient profile or the Consultations page.",
                "stethoscope")
    st.stop()

is_author = c.provider_name == actor.user.name and c.organization_name == actor.organization.name
page_header(c.complaint or "Draft consultation", f"{c.patient_name} · {fmt_datetime(c.date)}", eyebrow="Consultation details")

if c.status == "draft":
    html(f'<div class="hb-alert warning">{icon("edit_note", 20, fill=True)}<div><div class="t">Draft — not yet part of the clinical record</div>'
         '<div class="b">Only you can see this draft. Finish and save it to add it to the patient\'s timeline.</div></div></div>')
    if is_author and st.button("Continue editing", icon=":material/edit:", type="primary"):
        doctor.edit_consultation(c.id, c.patient_id)
    st.stop()

with st.container(horizontal=True, gap="small"):
    if st.button("Create prescription", icon=":material/prescriptions:", type="primary"):
        doctor.new_prescription(c.patient_id, c.id)
    if st.button("New consultation", icon=":material/add:"):
        doctor.new_consultation(c.patient_id)

left, right = st.columns([3, 2], gap="large")
with left:
    fields = [("Reason for visit", c.complaint), ("Symptoms / notes", c.notes), ("Observations", c.observations),
              ("Assessment", c.assessment), ("Diagnosis", c.diagnosis), ("Treatment plan", c.treatment_plan),
              ("Follow-up", c.follow_up)]
    rows = "".join(f'<div style="padding:.6rem 0;border-bottom:1px solid var(--hb-border)"><div class="hb-form-section" style="margin:0">{esc(k)}</div>'
                   f'<div style="font-size:.92rem;margin-top:.2rem;white-space:pre-wrap">{esc(v) if v else "<span style=color:var(--hb-muted)>Not documented</span>"}</div></div>'
                   for k, v in fields)
    html(f"""<div class="hb-card">
      <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center;flex-wrap:wrap">
        <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">{org_badge_html(c.organization_name, c.organization_type)}
          <span style="font-weight:600">{esc(c.provider_name)}</span></div>
        <span>{verified_badge_html("Clinical record")} {badge_html(fmt_datetime(c.date), "neutral", "schedule")}</span></div>
      <div class="hb-kv" style="margin:.8rem 0 .2rem"><span class="k">Patient</span><span class="v">{esc(c.patient_name)}</span>
        <span class="k">Doctor</span><span class="v">{esc(c.provider_name)}</span>
        <span class="k">Organization</span><span class="v">{esc(c.organization_name)}</span></div>
      {rows}</div>""")

with right:
    section_header("Clinical notes", "Clinician-authored · never edited by AI")
    html(f'<div class="hb-card" style="padding-top:.3rem">{notes_list_html(notes) or "<div style=padding-top:.6rem;color:var(--hb-muted);font-size:.85rem>No notes yet.</div>"}</div>')
    with st.container(key="hbform_note"):
        with st.form("add_note", clear_on_submit=True, border=False):
            st.markdown(f'<div class="hb-form-section">{icon("note_add", 14)} Add clinical note</div>', unsafe_allow_html=True)
            note_type = st.selectbox("Note type", list(NOTE_TYPES), format_func=NOTE_TYPES.__getitem__)
            content = st.text_area("Note", height=90, placeholder=f"Written by {actor.user.name}")
            if st.form_submit_button("Save note", icon=":material/save:", type="primary"):
                try:
                    with get_session() as s:
                        clinical_service.add_note(s, actor, c.patient_id, note_type, content, consultation_id=c.id)
                    ss["hb_flash"] = "Clinical note added to the patient's timeline."
                    st.rerun()
                except ClinicalValidationError as exc:
                    st.error(" ".join(exc.errors.values()))

    section_header("Attachments")
    for d in docs:
        with card(f"doc_{d.id}"):
            html(document_card_html(d))
            if d.has_file:
                with get_session() as s:
                    data, name, mime = document_service.read_file(s, actor, d.id)
                st.download_button("Download", data, file_name=name, mime=mime, key=f"dl_{d.id}", icon=":material/download:")
    if not docs:
        html('<div style="font-size:.85rem;color:var(--hb-muted)">No attachments.</div>')
    with st.container(key="hbform_upload"):
        with st.form("upload_doc", clear_on_submit=True, border=False):
            st.markdown(f'<div class="hb-form-section">{icon("upload_file", 14)} Upload document</div>', unsafe_allow_html=True)
            f = st.file_uploader("PDF, PNG or JPG (max 10 MB)", type=["pdf", "png", "jpg", "jpeg"], max_upload_size=10)
            t = st.text_input("Title", placeholder="e.g. Referral letter")
            dt = st.selectbox("Type", list(DOC_TYPES), format_func=DOC_TYPES.__getitem__)
            if st.form_submit_button("Upload", icon=":material/upload:"):
                if f is None:
                    st.error("Choose a file to upload.")
                else:
                    try:
                        with get_session() as s:
                            document_service.upload(s, actor, c.patient_id, file_name=f.name, data=f.getvalue(),
                                                    doc_type=dt, title=t or f.name, consultation_id=c.id)
                        ss["hb_flash"] = f"Uploaded by {actor.user.name} · {actor.organization.name}"
                        st.rerun()
                    except ClinicalValidationError as exc:
                        st.error(" ".join(exc.errors.values()))
