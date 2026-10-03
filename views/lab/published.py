import streamlit as st

from core.db import get_session
from core.models import LabOrderStatus
from services import lab_service
from ui.components import empty_state, lab_report_card, page_header
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    published = lab_service.list_orders(s, actor, [LabOrderStatus.PUBLISHED])

page_header("Published Reports", "Reports published to patients' HealthBridge timelines", eyebrow="Laboratory")
if not published:
    empty_state("No published reports", icon_name="lab_profile")
cols = st.columns(2)
for i, o in enumerate(published):
    with cols[i % 2]:
        lab_report_card(o, show_patient=True)
