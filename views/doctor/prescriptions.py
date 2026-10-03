import streamlit as st

from core.db import get_session
from services import provider_service
from ui import doctor
from ui.components import card, empty_state, html, kpi_row, page_header, prescription_card_html
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    rxs = provider_service.my_prescriptions(s, actor, include_drafts=True)

drafts = [rx for rx in rxs if rx.status == "draft"]
issued = [rx for rx in rxs if rx.status == "issued"]
others = [rx for rx in rxs if rx.status not in ("draft", "issued")]

head, actions = st.columns([3, 1], vertical_alignment="bottom")
with head:
    page_header("Prescriptions", "E-prescriptions you wrote. Drafts are private; issued prescriptions join the "
                "patient's timeline.", eyebrow="Clinical")
with actions, st.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Create Prescription", icon=":material/add:", type="primary"):
        doctor.new_prescription(st.session_state.get("sel_patient"))

kpi_row([
    dict(label="Drafts", value=len(drafts), icon_name="edit_note", tone="amber", foot=f"At {actor.organization.name}"),
    dict(label="Issued", value=len(issued), icon_name="verified", tone="teal", foot="Awaiting the patient's pharmacy choice"),
    dict(label="With pharmacy or dispensed", value=len(others), icon_name="local_pharmacy", tone="blue", foot="Phase 3 workflow"),
])
st.write("")


def grid(rows, empty: str, key: str) -> None:
    if not rows:
        empty_state(empty, icon_name="prescriptions")
        return
    cols = st.columns(3)
    for i, rx in enumerate(rows):
        with cols[i % 3], card(f"{key}_{rx.id}"):
            html(prescription_card_html(rx))
            label = "Continue draft" if rx.status == "draft" else "View details"
            if st.button(label, key=f"{key}_open_{rx.id}", icon=":material/open_in_new:", width="stretch",
                         type="primary" if rx.status == "draft" else "secondary"):
                doctor.view_prescription(rx.id)


t_draft, t_issued, t_all = st.tabs([f"Drafts ({len(drafts)})", f"Issued ({len(issued)})", f"All ({len(rxs)})"])
with t_draft:
    grid(drafts, "No draft prescriptions", "d")
with t_issued:
    grid(issued, "No issued prescriptions yet", "i")
with t_all:
    grid(rxs, "No prescriptions yet", "a")
