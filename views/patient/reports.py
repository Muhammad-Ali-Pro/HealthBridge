import streamlit as st

from core.db import get_session
from services import record_service
from ui.components import alert_card, empty_state, lab_report_card, page_header, section_header
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)
published = [o for o in record.reports if o.status == "published"]
pending = [o for o in record.reports if o.status != "published"]

page_header("Lab Reports", "Laboratory and imaging reports, published directly to your timeline by the laboratory.",
            eyebrow="My HealthBridge")

if pending:
    section_header("Being processed", f"{len(pending)} in progress")
    for o in pending:
        alert_card(f"{o.test_name} — at {o.lab_name}",
                   f"Ordered by {o.provider_name} ({o.organization_name}). Your report will appear here as soon as "
                   "the laboratory publishes it.", "info", "hourglass_top")

section_header("Published reports", f"{len(published)} available")
if not published:
    empty_state("No reports yet", icon_name="lab_profile")
cols = st.columns(2)
for i, o in enumerate(published):
    with cols[i % 2]:
        lab_report_card(o, plain=True)
