import streamlit as st

from core.db import get_session
from services import pharmacy_service
from ui.components import STATUS_STYLE, empty_state, page_header, prescription_card
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    rxs = pharmacy_service.list_prescriptions(s, actor)

page_header("Prescriptions", f"Every e-prescription sent to {actor.organization.name}", eyebrow="Pharmacy")
filters = ["all", "sent", "verified", "dispensed"]
counts = {f: len(rxs) if f == "all" else sum(rx.status == f for rx in rxs) for f in filters}
choice = st.segmented_control("Status", filters, default="all", required=True, key="ph_filter", label_visibility="collapsed",
                              format_func=lambda f: f"{'All' if f == 'all' else STATUS_STYLE[f][0]} ({counts[f]})")
shown = rxs if choice == "all" else [rx for rx in rxs if rx.status == choice]
st.write("")
if not shown:
    empty_state("No prescriptions here", icon_name="prescriptions")
cols = st.columns(3)
for i, rx in enumerate(shown):
    with cols[i % 3]:
        prescription_card(rx)
