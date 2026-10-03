import streamlit as st

from core.db import get_session
from core.models import DocumentType
from services import access_service, clinical_service, document_service, patient_service, prescription_service
from services.clinical_service import ClinicalValidationError, ConsultationInput
from ui import doctor
from ui.components import allergy_chips_html, esc, html, icon, org_badge_html, page_header
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state
draft_id = ss.get("sel_edit_consultation")
errors: dict[str, str] = ss.get("consult_errors", {})

DOC_TYPES = {DocumentType.MEDICAL_REPORT: "Medical report", DocumentType.REFERRAL_LETTER: "Referral letter",
             DocumentType.IMAGING_REPORT: "Imaging report", DocumentType.LAB_REPORT: "External lab report",
             DocumentType.DISCHARGE_SUMMARY: "Discharge summary", DocumentType.OTHER: "Other"}

if st.button("Back", icon=":material/arrow_back:", type="tertiary", key="ce_back"):
    ss.pop("sel_edit_consultation", None)
    ss.pop("consult_errors", None)
    st.switch_page(doctor.PATIENTS if ss.get("sel_patient") else "views/doctor/consultations.py")
page_header("Continue draft consultation" if draft_id else "New consultation",
            "Organization, provider, patient and time are captured automatically from your working context.",
            eyebrow="Consultations")

# --- Patient (pre-selected from the profile, or chosen here among consented patients) ---------
draft = None
if draft_id:
    with get_session() as s:
        draft = clinical_service.get_consultation(s, actor, draft_id)
    patient_id = draft.patient_id
    ss["sel_patient"] = patient_id
else:
    with st.container(key="hbform_patient"):
        patient_id = doctor.pick_patient(actor, key="ce_patient")
if not patient_id:
    st.stop()

with get_session() as s:
    decision = access_service.authorize(s, actor, patient_id)
    identity = next(e.patient for e in patient_service.directory(s, actor) if e.patient.id == patient_id)
    allergies = prescription_service.patient_allergies(s, actor, patient_id) if decision.allowed else []
if not decision.allowed:
    doctor.consent_banner(actor, decision, identity.name)
    st.stop()

org = actor.organization
html(f"""<div class="hb-card" style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center">
  <div><div class="hb-form-section">{icon("person", 14)} Patient</div><div style="font-weight:800;font-size:1.05rem">{esc(identity.name)}</div>
    <div style="font-size:.8rem;color:var(--hb-muted)">{esc(identity.display_id)} · {identity.age} yrs · {esc(identity.sex.title())}</div></div>
  <div><div class="hb-form-section">{icon("stethoscope", 14)} Provider</div><div style="font-weight:600">{esc(actor.user.name)}</div></div>
  <div><div class="hb-form-section">{icon("domain", 14)} Organization</div>{org_badge_html(org.name, org.org_type)}</div>
  <div><div class="hb-form-section">{icon("warning", 14)} Allergies</div>{allergy_chips_html(allergies)}</div>
</div>""")
if errors:
    html(f'<div class="hb-alert danger">{icon("error", 20, fill=True)}<div><div class="t">Please complete the highlighted fields</div>'
         f'<div class="b">{esc(" ".join(errors.values()))}</div></div></div>')


def value(field: str) -> str:
    return getattr(draft, field, "") if draft else ""


def section(title: str, ic: str):
    st.markdown(f'<div class="hb-form-section">{icon(ic, 14)} {esc(title)}</div>', unsafe_allow_html=True)


with st.form("consultation_form", border=False):
    with st.container(key="hbform_visit"):
        section("Visit information", "event_note")
        complaint = st.text_input("Reason for visit *", value=value("complaint"), placeholder="e.g. Chest discomfort on exertion")
        doctor.show_errors(errors, "complaint")
        notes = st.text_area("Symptoms / clinical notes", value=value("notes"), height=110,
                             placeholder="History of presenting complaint, symptoms, relevant history…")
    with st.container(key="hbform_exam"):
        section("Clinical observations", "monitor_heart")
        observations = st.text_area("Observations / examination", value=value("observations"), height=90,
                                    placeholder="Vital signs, examination findings, bedside tests…")
    with st.container(key="hbform_assess"):
        section("Assessment & diagnosis", "clinical_notes")
        a, b = st.columns(2)
        assessment = a.text_area("Assessment", value=value("assessment"), height=100, placeholder="Clinical assessment")
        diagnosis = b.text_area("Diagnosis", value=value("diagnosis"), height=100, placeholder="Working or confirmed diagnosis")
        doctor.show_errors(errors, "assessment")
    with st.container(key="hbform_plan"):
        section("Treatment plan & follow-up", "event_available")
        plan = st.text_area("Treatment plan", value=value("treatment_plan"), height=90,
                            placeholder="Management plan, investigations, advice…")
        follow_up = st.text_area("Follow-up instructions", value=value("follow_up"), height=70,
                                 placeholder="e.g. Review in 2 weeks, or sooner if symptoms worsen")
    with st.container(key="hbform_attach"):
        section("Attachments (optional)", "attach_file")
        upload = st.file_uploader("Attach a document (PDF, PNG or JPG, max 10 MB)", type=["pdf", "png", "jpg", "jpeg"],
                                  max_upload_size=10)
        c1, c2 = st.columns([2, 1])
        doc_title = c1.text_input("Document title", placeholder="e.g. Resting ECG")
        doc_type = c2.selectbox("Document type", list(DOC_TYPES), format_func=DOC_TYPES.__getitem__)
        doctor.show_errors(errors, "file")
        st.caption("Attachments are added when you save the consultation (not on drafts).")
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        save_draft = st.form_submit_button("Save draft", icon=":material/save:")
        save_final = st.form_submit_button("Save consultation", icon=":material/check_circle:", type="primary")

if save_draft or save_final:
    data = ConsultationInput(complaint=complaint, notes=notes, observations=observations, assessment=assessment,
                             diagnosis=diagnosis, treatment_plan=plan, follow_up=follow_up)
    try:
        with get_session() as s:
            saved = clinical_service.save_consultation(s, actor, patient_id, data, finalize=save_final,
                                                       consultation_id=draft_id)
            if save_final and upload is not None:
                document_service.upload(s, actor, patient_id, file_name=upload.name, data=upload.getvalue(),
                                        doc_type=doc_type, title=doc_title or upload.name, consultation_id=saved.id)
    except ClinicalValidationError as exc:
        ss["consult_errors"] = exc.errors
        st.rerun()
    ss.pop("consult_errors", None)
    if save_final:
        ss.pop("sel_edit_consultation", None)
        ss["hb_flash"] = "Consultation saved to the patient's timeline."
        doctor.view_consultation(saved.id)
    else:
        ss["sel_edit_consultation"] = saved.id
        ss["hb_flash"] = "Draft saved. Drafts are private and not part of the clinical record."
        st.rerun()

if draft_id:
    if st.button("Discard draft", icon=":material/delete:", type="tertiary"):
        with get_session() as s:
            clinical_service.discard_draft(s, actor, draft_id)
        ss.pop("sel_edit_consultation", None)
        ss["hb_flash"] = "Draft discarded."
        st.switch_page("views/doctor/consultations.py")
