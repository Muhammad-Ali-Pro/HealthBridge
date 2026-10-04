import streamlit as st

from core.db import get_session
from services import prescription_service, record_service
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError
from ui.components import card, empty_state, html, page_header, prescription_card_html, section_header
from ui.rx_status import patient_plain_status, pharmacy_updates_html
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state
with get_session() as s:
    record = record_service.own_record(s, actor)
    pharmacies = prescription_service.available_pharmacies(s)
names = {p.id: p.name for p in pharmacies}


def _dismiss() -> None:
    ss.pop("pt_rx_send", None)


@st.dialog("Send prescription to a pharmacy", on_dismiss=_dismiss)
def confirm_send(rx_id: int, pharmacy_id: int) -> None:
    rx = next(r for r in record.prescriptions if r.id == rx_id)
    st.markdown(f"Send **{rx.display_id}** ({', '.join(i.drug_name for i in rx.items)}) to **{names[pharmacy_id]}**?")
    st.caption(f"Only {names[pharmacy_id]} receives it — the medicines, how to take them and your allergies. "
               "Never your medical history.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch", key="pt_send_cancel"):
        _dismiss()
        st.rerun()
    if c2.button("Send prescription", type="primary", width="stretch", icon=":material/send:", key="pt_send_ok"):
        _dismiss()
        try:
            with get_session() as s:
                prescription_service.send_to_pharmacy(s, actor, rx_id, pharmacy_id)
            ss["hb_flash"] = f"Sent to {names[pharmacy_id]}."
        except (ClinicalValidationError, AccessDenied) as exc:
            ss["hb_flash"] = f"Could not send: {exc}"
        st.rerun()


page_header("Prescriptions", "Every prescription written for you — where it is, and who has it.", eyebrow="My HealthBridge")
to_send = [rx for rx in record.prescriptions if rx.status == "issued"]
others = [rx for rx in record.prescriptions if rx.status != "issued"]

if to_send:
    section_header("Choose a pharmacy", "Only the pharmacy you choose receives the prescription")
    for rx in to_send:
        with card(f"send_{rx.id}"):
            html(prescription_card_html(rx, show_patient=False, plain_status=patient_plain_status(rx), progress=True))
            a, b = st.columns([3, 1], vertical_alignment="bottom")
            labels = {p.id: f"{p.name} — {p.address.split(',')[0]}" if p.address else p.name for p in pharmacies}
            choice = a.selectbox("Pharmacy", list(labels), format_func=labels.__getitem__, key=f"pharm_{rx.id}")
            if b.button("Send Prescription", key=f"send_{rx.id}", icon=":material/send:", type="primary", width="stretch"):
                ss["pt_rx_send"] = (rx.id, choice)

section_header("All prescriptions", f"{len(others)} prescriptions")
if not others:
    empty_state("No prescriptions yet", icon_name="prescriptions")
cols = st.columns(2)
for i, rx in enumerate(others):
    with cols[i % 2], card(f"rx_{rx.id}"):
        html(prescription_card_html(rx, show_patient=False, plain_status=patient_plain_status(rx), progress=True))
        updates = pharmacy_updates_html(rx)   # status only — no invoice line items or prices here
        if updates:
            with st.expander("Pharmacy updates", icon=":material/local_pharmacy:"):
                html(updates)
html('<div style="font-size:.78rem;color:var(--hb-muted)">Pharmacies see only what they need to fill a prescription — '
     'never your full history.</div>')

if ss.get("pt_rx_send"):
    rx_id, pharmacy_id = ss["pt_rx_send"]
    if any(r.id == rx_id and r.status == "issued" for r in record.prescriptions):
        confirm_send(rx_id, pharmacy_id)
    else:
        _dismiss()
