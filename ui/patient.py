"""Patient-side actions shared by Home, My Health and Documents: add patient-provided information, upload a document.

Dialogs are opened through a session flag (`pt_dialog`) so they survive reruns; dismissing clears the flag.
Everything saved here is patient-provided and never changes clinician-documented data.
"""

import streamlit as st

from core.db import get_session
from core.models import DocumentType, PatientEntryType
from services import document_service, patient_entry_service
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError
from ui.components import alert_card, html, icon, patient_provided_badge_html

ss = st.session_state

ENTRY_TYPES = [PatientEntryType.NOTE, PatientEntryType.ALLERGY, PatientEntryType.CONDITION,
               PatientEntryType.MEDICATION, PatientEntryType.OTHER]
ENTRY_LABELS = patient_entry_service.ENTRY_LABELS
DOC_TYPES = {DocumentType.MEDICAL_REPORT: "Medical report", DocumentType.LAB_REPORT: "Lab report (external)",
             DocumentType.IMAGING_REPORT: "Imaging report", DocumentType.REFERRAL_LETTER: "Referral letter",
             DocumentType.DISCHARGE_SUMMARY: "Discharge summary", DocumentType.PRESCRIPTION: "Prescription (paper)",
             DocumentType.OTHER: "Other"}


def _close() -> None:
    for k in [k for k in ss if k in ("pt_dialog", "pt_entry_type", "pt_errors")
              or k.startswith(("pt_entry_", "pt_upload_"))]:
        ss.pop(k, None)


def open_entry(entry_type: str = PatientEntryType.NOTE) -> None:
    ss["pt_dialog"], ss["pt_entry_type"] = "entry", entry_type
    ss.pop("pt_errors", None)


def open_upload() -> None:
    ss["pt_dialog"] = "upload"
    ss.pop("pt_errors", None)


def _errors(field: str) -> None:
    msg = ss.get("pt_errors", {}).get(field)
    if msg:
        st.markdown(f'<div class="hb-field-error">{icon("error", 14)} {msg}</div>', unsafe_allow_html=True)


@st.dialog("Add to my health record", on_dismiss=_close)
def entry_dialog(actor) -> None:
    html(f'<div style="margin-bottom:.5rem">{patient_provided_badge_html()}</div>')
    st.caption("This is added as patient-provided information. Your doctors see it marked as reported by you, "
               "not verified by a clinician.")
    current = ss.get("pt_entry_type", PatientEntryType.NOTE)
    with st.form("pt_entry_form", border=False):
        entry_type = st.selectbox("What are you adding?", ENTRY_TYPES, index=ENTRY_TYPES.index(current),
                                  format_func=lambda t: ENTRY_LABELS[t], key="pt_entry_kind")
        title = st.text_input("Title *", placeholder="e.g. Ibuprofen  ·  Home blood pressure readings", key="pt_entry_title")
        _errors("title")
        details = st.text_area("Details", placeholder="e.g. Rash after taking it in 2024  ·  130/85 most mornings",
                               key="pt_entry_details", height=100)
        _errors("details")
        st.caption("Allergies you add here never replace the allergies your doctors have recorded.")
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", width="stretch")
        save = c2.form_submit_button("Save", type="primary", width="stretch", icon=":material/check:")
    if cancel:
        _close()
        st.rerun()
    if save:
        try:
            with get_session() as s:
                patient_entry_service.add_entry(s, actor, entry_type, title, details)
        except ClinicalValidationError as exc:
            ss["pt_errors"] = exc.errors
            ss["pt_entry_type"] = entry_type
            st.rerun()
        except AccessDenied as exc:
            alert_card("Could not save", str(exc), "danger")
            return
        _close()
        ss["hb_flash"] = f"{ENTRY_LABELS[entry_type]} added to your record."
        st.rerun()


@st.dialog("Upload a document", on_dismiss=_close)
def upload_dialog(actor) -> None:
    html(f'<div style="margin-bottom:.5rem">{patient_provided_badge_html("Added by you")}</div>')
    st.caption("Uploaded documents are marked as patient-provided. Doctors see them only if you share Documents.")
    with st.form("pt_upload_form", border=False):
        upload = st.file_uploader("File (PDF, PNG or JPG, max 10 MB) *", type=["pdf", "png", "jpg", "jpeg"],
                                  max_upload_size=10, key="pt_upload_file")
        _errors("file")
        title = st.text_input("Title *", placeholder="e.g. Blood pressure diary", key="pt_upload_title")
        _errors("title")
        doc_type = st.selectbox("Type", list(DOC_TYPES), format_func=DOC_TYPES.__getitem__, key="pt_upload_type")
        description = st.text_area("Description", height=70, key="pt_upload_desc")
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", width="stretch")
        save = c2.form_submit_button("Upload", type="primary", width="stretch", icon=":material/upload:")
    if cancel:
        _close()
        st.rerun()
    if save:
        try:
            with get_session() as s:
                document_service.upload_own(s, actor, file_name=upload.name if upload else "", data=upload.getvalue()
                                            if upload else b"", doc_type=doc_type, title=title, description=description)
        except ClinicalValidationError as exc:
            ss["pt_errors"] = exc.errors
            st.rerun()
        _close()
        ss["hb_flash"] = "Document added to your record."
        st.rerun()


def quick_actions(actor, key: str, upload: bool = True, entries: bool = True) -> None:
    """Buttons that open the patient dialogs (render inside a horizontal container)."""
    if upload:
        st.button("Upload a document", icon=":material/upload_file:", key=f"{key}_upload", on_click=open_upload)
    if entries:
        st.button("Add a health note", icon=":material/edit_note:", key=f"{key}_note", on_click=open_entry,
                  args=(PatientEntryType.NOTE,))
        st.button("Add allergy or information", icon=":material/add_circle:", key=f"{key}_info", on_click=open_entry,
                  args=(PatientEntryType.ALLERGY,))


def render_dialogs(actor) -> None:
    """Call once per page, after the page content."""
    if ss.get("pt_dialog") == "entry":
        entry_dialog(actor)
    elif ss.get("pt_dialog") == "upload":
        upload_dialog(actor)
