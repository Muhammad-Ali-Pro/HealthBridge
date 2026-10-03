import streamlit as st

from core.db import get_session
from core.models import LabOrderStatus
from services import lab_service
from ui.components import page_header
from ui.shell import current_actor
from ui.workflows import lab_detail, lab_order_card_html, master_detail

actor = current_actor()
with get_session() as s:
    resulted = lab_service.list_orders(s, actor, [LabOrderStatus.RESULTED])
    verified = lab_service.list_orders(s, actor, [LabOrderStatus.VERIFIED])

page_header("Pending Reports", "Verify results, then publish the report to the patient's HealthBridge timeline",
            eyebrow="Laboratory")
t1, t2 = st.tabs([f"Awaiting verification ({len(resulted)})", f"Ready to publish ({len(verified)})"])
with t1:
    master_detail("lab_res", resulted, lab_order_card_html, lab_detail, "No results awaiting verification")
with t2:
    master_detail("lab_ver", verified, lab_order_card_html, lab_detail, "No reports ready to publish")
