import streamlit as st

from core.db import get_session
from core.models import LabOrderStatus
from services import document_service, provider_service
from ui.components import (
    CATEGORY_STYLE,
    DOC_TYPE_LABELS,
    data_table,
    empty_state,
    esc,
    fmt_date,
    lab_report_card,
    org_badge_html,
    page_header,
    patient_provided_badge_html,
    phase_action,
    section_header,
)
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    orders = provider_service.my_lab_orders(s, actor)
    docs = document_service.authorized_documents(s, actor)
ready = [o for o in orders if o.status == LabOrderStatus.PUBLISHED]
pending = [o for o in orders if o.status != LabOrderStatus.PUBLISHED]

head, actions = st.columns([3, 1], vertical_alignment="bottom")
with head:
    page_header("Reports & Documents", f"Documents you are authorized to see at {actor.organization.name}, and the "
                "tests you ordered here.", eyebrow="Clinical")
with actions, st.container(horizontal=True, horizontal_alignment="right"):
    phase_action("Order lab test", "biotech", 4, key="order_lab")

t_docs, t_ready, t_pending = st.tabs([f"Documents ({len(docs)})", f"Lab results ready ({len(ready)})",
                                      f"Tests in progress ({len(pending)})"])
with t_docs:
    st.caption("Only documents within each patient's consent to you at this organization, plus documents you uploaded. "
               "Upload new documents from a consultation.")
    data_table(["Document", "Patient", "Source", "Organization", "Uploaded by", "Date", "Category"], [[
        f'<span class="strong">{esc(d.title)}</span><div class="muted">{esc(DOC_TYPE_LABELS.get(d.doc_type, "Document"))}'
        f'{" · " + esc(d.file_name) if d.file_name else ""}</div>',
        f'{esc(p.name)}<div class="muted">{esc(p.display_id)}</div>',
        patient_provided_badge_html("Patient uploaded") if d.source_type == "patient" else esc(d.source),
        org_badge_html(d.organization_name, d.organization_type) or "—",
        esc(d.uploaded_by_name),
        esc(fmt_date(d.created_at)),
        esc(CATEGORY_STYLE.get(d.record_category, (d.record_category,))[0]),
    ] for p, d in docs], empty="No documents you are authorized to see")
    files = [(p, d) for p, d in docs if d.has_file]
    if files:
        section_header("Download")
        labels = {d.id: f"{d.title} · {p.name}" for p, d in files}
        chosen = st.selectbox("Document", list(labels), format_func=labels.__getitem__, label_visibility="collapsed")
        with get_session() as s:
            data, name, mime = document_service.read_file(s, actor, chosen)
        st.download_button("Download file", data, file_name=name, mime=mime, icon=":material/download:")
for tab, rows, show_values in ((t_ready, ready, True), (t_pending, pending, False)):
    with tab:
        if not rows:
            empty_state("Nothing here", icon_name="lab_profile")
        cols = st.columns(2)
        for i, o in enumerate(rows):
            with cols[i % 2]:
                lab_report_card(o, show_patient=True, show_values=show_values)
