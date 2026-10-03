import streamlit as st

from core.db import get_session
from services import pharmacy_service
from ui.components import page_header, prescription_card_html
from ui.shell import current_actor
from ui.workflows import master_detail, minimum_necessary_note, pharmacy_detail

actor = current_actor()
with get_session() as s:
    awaiting = pharmacy_service.list_prescriptions(s, actor, pharmacy_service.AWAITING)
    ready = pharmacy_service.list_prescriptions(s, actor, pharmacy_service.READY)

page_header("Pending Verification", "Check each incoming e-prescription, then dispense", eyebrow="Pharmacy")
minimum_necessary_note(actor.organization.name)
t1, t2 = st.tabs([f"Awaiting verification ({len(awaiting)})", f"Ready to dispense ({len(ready)})"])
with t1:
    master_detail("ph_await", awaiting, prescription_card_html, pharmacy_detail, "No prescriptions awaiting verification")
with t2:
    master_detail("ph_ready", ready, prescription_card_html, pharmacy_detail, "Nothing ready to dispense")
