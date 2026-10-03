import streamlit as st

from core.db import get_session
from core.models import OrgType
from services import record_service, user_service
from ui.components import card, empty_state, fmt_date, html, page_header, phase_action, prescription_card_html, section_header
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)
    pharmacies = user_service.list_organizations(s, OrgType.PHARMACY)


def plain_status(rx) -> str:
    pharmacy = rx.pharmacy_name or "your pharmacy"
    billing = ""
    if rx.invoice:
        billing = f" Invoice {rx.invoice.invoice_number}: {rx.invoice.payment_status.replace('_', ' ')}."
    return {
        "issued": "Ready to send. Choose the pharmacy where you want to collect your medicine.",
        "sent": f"Sent to {pharmacy}. The pharmacist will check it before it's ready.",
        "verified": f"Checked by {pharmacy} and ready for you to collect.",
        "partially_dispensed": f"Part of your medicine was collected from {pharmacy}.",
        "dispensed": f"Collected from {pharmacy}" + (f" on {fmt_date(rx.dispensed_at)}." if rx.dispensed_at else ".") + billing,
        "rejected": f"{pharmacy} could not fill this prescription. Please contact your doctor.",
        "cancelled": "Your doctor cancelled this prescription.",
    }.get(rx.status, "")


page_header("Prescriptions", "Every prescription written for you — where it is, and who has it.", eyebrow="My HealthBridge")
to_send = [rx for rx in record.prescriptions if rx.status == "issued"]
others = [rx for rx in record.prescriptions if rx.status != "issued"]

if to_send:
    section_header("Choose a pharmacy", "Only the pharmacy you choose receives the prescription")
    for rx in to_send:
        with card(f"send_{rx.id}"):
            html(prescription_card_html(rx, show_patient=False, plain_status=plain_status(rx), progress=True))
            a, b = st.columns([3, 1], vertical_alignment="bottom")
            labels = {p.id: f"{p.name} — {p.address.split(',')[0]}" for p in pharmacies}
            a.selectbox("Pharmacy", list(labels), format_func=labels.__getitem__, key=f"pharm_{rx.id}")
            with b:
                phase_action("Send Prescription", "send", 2, key=f"send_{rx.id}", primary=True, stretch=True)

section_header("All prescriptions", f"{len(others)} prescriptions")
if not others:
    empty_state("No prescriptions yet", icon_name="prescriptions")
cols = st.columns(2)
for i, rx in enumerate(others):
    with cols[i % 2]:
        html(f'<div class="hb-card">{prescription_card_html(rx, show_patient=False, plain_status=plain_status(rx), progress=True)}</div>')
html('<div style="font-size:.78rem;color:var(--hb-muted)">Pharmacies see only what they need to fill a prescription — '
     'never your full history.</div>')
