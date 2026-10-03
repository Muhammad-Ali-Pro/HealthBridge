import streamlit as st

from core.db import get_session
from core.models import LabOrderStatus
from services import lab_service
from ui.components import page_header
from ui.shell import current_actor
from ui.workflows import lab_detail, lab_order_card_html, master_detail

actor = current_actor()
with get_session() as s:
    new = lab_service.list_orders(s, actor, [LabOrderStatus.ORDERED])
    in_progress = lab_service.list_orders(s, actor, [LabOrderStatus.RECEIVED])

page_header("Test Orders", f"Orders sent to {actor.organization.name} by doctors at clinics and hospitals", eyebrow="Laboratory")
t1, t2 = st.tabs([f"New orders ({len(new)})", f"In progress ({len(in_progress)})"])
with t1:
    master_detail("lab_new", new, lab_order_card_html, lab_detail, "No new orders")
with t2:
    master_detail("lab_prog", in_progress, lab_order_card_html, lab_detail, "Nothing in progress")
