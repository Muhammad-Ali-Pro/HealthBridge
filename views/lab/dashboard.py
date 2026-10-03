from datetime import datetime

import streamlit as st

from core.db import get_session
from services import lab_service
from ui.components import empty_state, html, kpi_row, page_header, quick_actions, section_header
from ui.shell import current_actor
from ui.workflows import lab_order_card_html

actor = current_actor()
lab = actor.organization.name
with get_session() as s:
    ov = lab_service.overview(s, actor)
    open_orders = lab_service.list_orders(s, actor, lab_service.OPEN_ORDERS)
    pending = lab_service.list_orders(s, actor, lab_service.PENDING_REPORTS)

hour = datetime.now().hour
greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
page_header(f"{greeting}, {actor.user.name.split()[0]}", f"{lab} · {datetime.now():%A, %d %B %Y}", eyebrow="Laboratory workspace")
quick_actions([
    ("views/lab/orders.py", "Process test orders", "inbox"),
    ("views/lab/pending.py", "Verify & publish reports", "pending_actions"),
    ("views/lab/published.py", "Published reports", "lab_profile"),
], key="lab")
st.write("")
kpi_row([
    dict(label="New orders", value=ov["new_orders"], icon_name="inbox", tone="blue", foot="Awaiting sample"),
    dict(label="In progress", value=ov["in_progress"], icon_name="science", tone="navy", foot="Sample received"),
    dict(label="Awaiting verification", value=ov["awaiting_verification"], icon_name="pending_actions", tone="amber",
         foot="Results entered"),
    dict(label="Ready to publish", value=ov["ready_to_publish"], icon_name="publish", tone="teal", foot="Verified"),
])
st.write("")
left, right = st.columns(2, gap="large")
with left:
    section_header("Test orders", f"{len(open_orders)} open")
    for o in open_orders:
        html(f'<div class="hb-card">{lab_order_card_html(o)}</div>')
    if not open_orders:
        empty_state("No open orders", icon_name="inbox")
with right:
    section_header("Reports to verify or publish", f"{len(pending)} pending")
    for o in pending:
        html(f'<div class="hb-card">{lab_order_card_html(o)}</div>')
    if not pending:
        empty_state("Nothing pending", icon_name="pending_actions")
