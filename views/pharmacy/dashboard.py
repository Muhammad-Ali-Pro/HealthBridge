from datetime import datetime

import streamlit as st

from core.db import get_session
from core.models import PrescriptionStatus
from services import pharmacy_service
from ui.components import empty_state, esc, fmt_when, html, kpi_row, page_header, prescription_card, quick_actions, section_header
from ui.shell import current_actor
from ui.workflows import minimum_necessary_note

actor = current_actor()
pharmacy = actor.organization.name
with get_session() as s:
    ov = pharmacy_service.queue_overview(s, actor)
    queue = pharmacy_service.list_prescriptions(s, actor, [PrescriptionStatus.SENT, PrescriptionStatus.VERIFIED])
    dispensed = pharmacy_service.list_prescriptions(s, actor, [PrescriptionStatus.DISPENSED])

hour = datetime.now().hour
greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
page_header(f"{greeting}, {actor.user.name.split()[0]}", f"{pharmacy} · {datetime.now():%A, %d %B %Y}",
            eyebrow="Pharmacy workspace")
minimum_necessary_note(pharmacy)
quick_actions([
    ("views/pharmacy/pending.py", "Verify prescriptions", "fact_check"),
    ("views/pharmacy/prescriptions.py", "All prescriptions", "prescriptions"),
    ("views/pharmacy/dispensing.py", "Dispensing", "local_pharmacy"),
    ("views/pharmacy/billing.py", "Billing", "receipt_long"),
], key="pharmacy")
st.write("")
kpi_row([
    dict(label="Awaiting verification", value=ov["awaiting_verification"], icon_name="fact_check", tone="blue", foot="Pharmacist check needed"),
    dict(label="Ready to dispense", value=ov["ready_to_dispense"], icon_name="inventory_2", tone="amber", foot="Verified, not collected"),
    dict(label="Dispensed today", value=ov["dispensed_today"], icon_name="check_circle", tone="teal", foot="Completed handovers"),
    dict(label="Pending", value=ov["pending"], icon_name="pending_actions", tone="navy", foot="Not yet dispensed"),
])
st.write("")

left, right = st.columns([2, 1], gap="large")
with left:
    section_header("Prescription queue", f"{len(queue)} need attention")
    if not queue:
        empty_state("Queue is clear", "New e-prescriptions will appear here.", "inbox")
    cols = st.columns(2)
    for i, rx in enumerate(queue):
        with cols[i % 2]:
            prescription_card(rx)
with right:
    section_header("Recently dispensed")
    rows = "".join(f"""
      <div style="display:flex;justify-content:space-between;gap:.5rem;padding:.55rem 0;border-bottom:1px solid var(--hb-border)">
        <div><div style="font-weight:600;font-size:.86rem">{esc(rx.patient_name)}</div>
          <div style="font-size:.76rem;color:var(--hb-muted)">{esc(", ".join(i.drug_name for i in rx.items))}</div></div>
        <span style="font-size:.76rem;color:var(--hb-muted)">{esc(fmt_when(rx.dispensed_at or rx.created_at))}</span></div>"""
                   for rx in dispensed[:5])
    html(f'<div class="hb-card" style="padding-top:.4rem;padding-bottom:.4rem">{rows}</div>' if rows else "")
