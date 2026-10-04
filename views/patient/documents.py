import streamlit as st

from core.db import get_session
from services import document_service, record_service
from services.access_service import AccessDenied
from ui import patient as patient_actions
from ui.components import card, document_card_html, empty_state, html, org_badge_html, page_header, section_header
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)

FILTERS = {
    "All": lambda d: True,
    "From my doctors": lambda d: d.source_type == "provider",
    "From laboratories & pharmacies": lambda d: d.source_type == "organization",
    "Added by me": lambda d: d.source_type == "patient",
}

head, action = st.columns([3, 1.2], vertical_alignment="bottom")
with head:
    page_header("Documents", "Reports, letters and files from your providers — and the ones you added yourself.",
                eyebrow="My HealthBridge")
with action, st.container(horizontal=True, horizontal_alignment="right"):
    patient_actions.quick_actions(actor, key="docs", entries=False)

docs = record.documents
counts = {f: sum(map(fn, docs)) for f, fn in FILTERS.items()}
choice = st.segmented_control("Source", list(FILTERS), default="All", required=True, key="pt_docs_filter",
                              label_visibility="collapsed", format_func=lambda f: f"{f} ({counts[f]})")
shown = [d for d in docs if FILTERS[choice](d)]
section_header("My documents", f"{len(shown)} shown · every document keeps its source")
if not shown:
    empty_state("No documents here yet", "Use “Upload a document” to add one.", "description")
cols = st.columns(2)
for i, d in enumerate(shown):
    with cols[i % 2], card(f"doc_{d.id}"):
        html(document_card_html(d))
        if d.organization_name:
            html(f'<div style="margin-top:.45rem">{org_badge_html(d.organization_name, d.organization_type)}</div>')
        if d.has_file:
            try:
                with get_session() as s:
                    data, name, mime = document_service.read_file(s, actor, d.id)
                st.download_button("Download", data, file_name=name, mime=mime, key=f"dl_{d.id}",
                                   icon=":material/download:")
            except (FileNotFoundError, AccessDenied):
                st.caption("File not available in this demo.")
        else:
            st.caption("Demo record — no file attached.")
html('<div style="font-size:.78rem;color:var(--hb-muted)">Doctors see your documents only if you share '
     '“Documents” with them in Consent & Access.</div>')
patient_actions.render_dialogs(actor)
