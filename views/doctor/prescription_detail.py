import streamlit as st

from core.db import get_session
from services import clinical_service, prescription_service
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError
from ui import doctor
from ui.components import (
    alert_card,
    badge_html,
    data_table,
    empty_state,
    esc,
    fmt_datetime,
    html,
    org_badge_html,
    page_header,
    rx_progress_html,
    section_header,
    status_badge_html,
)
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state
rx_id = ss.get("sel_rx")

if st.button("All prescriptions", icon=":material/arrow_back:", type="tertiary"):
    st.switch_page("views/doctor/prescriptions.py")

try:
    with get_session() as s:
        rx = prescription_service.get_prescription(s, actor, rx_id) if rx_id else None
        linked = (clinical_service.get_consultation(s, actor, rx.consultation_id)
                  if rx and rx.consultation_id else None)
except AccessDenied as exc:
    page_header("Prescription", eyebrow="Prescriptions")
    doctor.locked_tab(f"This prescription ({exc})")
    st.stop()

if rx is None:
    page_header("Prescription", eyebrow="Prescriptions")
    empty_state("No prescription selected", "Open a prescription from the Prescriptions page.", "prescriptions")
    st.stop()

page_header(f"Prescription {rx.display_id}", f"{rx.patient_name} · {rx.patient_age} yrs · {rx.patient_sex.title()}",
            eyebrow="Prescription details")

if rx.status == "draft":
    alert_card("Draft — not yet issued", "Only you can see this draft. Issue it to add it to the patient's timeline.", "warning",
               "edit_note")
    with st.container(horizontal=True, gap="small"):
        if st.button("Continue editing", icon=":material/edit:", type="primary"):
            doctor.edit_prescription(rx.id, rx.patient_id)
        if st.button("Discard draft", icon=":material/delete:"):
            with get_session() as s:
                prescription_service.discard_draft(s, actor, rx.id)
            ss.pop("sel_rx", None)
            ss["hb_flash"] = "Draft prescription discarded."
            st.switch_page("views/doctor/prescriptions.py")

left, right = st.columns([3, 2], gap="large")
with left:
    html(f"""<div class="hb-card">
      <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center;flex-wrap:wrap">
        <div style="display:flex;gap:.5rem;align-items:center">{org_badge_html(rx.organization_name, rx.organization_type)}
          <span style="font-weight:600">{esc(rx.provider_name)}</span></div>{status_badge_html(rx.status)}</div>
      <div class="hb-kv" style="margin-top:.8rem"><span class="k">Patient</span><span class="v">{esc(rx.patient_name)}</span>
        <span class="k">Prescribing doctor</span><span class="v">{esc(rx.provider_name)}</span>
        <span class="k">Organization</span><span class="v">{esc(rx.organization_name)}</span>
        <span class="k">Prescription date</span><span class="v">{esc(fmt_datetime(rx.created_at))}</span>
        <span class="k">Issued</span><span class="v">{esc(fmt_datetime(rx.issued_at)) if rx.issued_at else "Not yet issued"}</span>
        <span class="k">Pharmacy</span><span class="v">{esc(rx.pharmacy_name or "Not sent yet")}</span>
        <span class="k">Notes</span><span class="v">{esc(rx.notes) or "—"}</span></div>
      {rx_progress_html(rx) if rx.status != "draft" else ""}</div>""")
    section_header("Medicines", f"{len(rx.items)} item{'s' if len(rx.items) != 1 else ''}")
    data_table(["Medicine", "Strength", "Dosage", "Route", "Frequency", "Duration", "Qty", "Instructions"], [[
        f'<span class="strong">{esc(i.drug_name)}</span>', esc(i.strength), esc(i.dosage or "—"), esc(i.route),
        esc(i.frequency), f"{i.duration_days} days", str(i.quantity), esc(i.instructions or "—")] for i in rx.items])
with right:
    section_header("Linked consultation")
    if linked:
        html(f"""<div class="hb-card"><div style="font-weight:700">{esc(linked.complaint)}</div>
             <div style="font-size:.82rem;color:var(--hb-navy-600);margin:.2rem 0 .5rem">{esc(linked.diagnosis or linked.assessment)}</div>
             {badge_html(fmt_datetime(linked.date), "neutral", "schedule")}</div>""")
        if st.button("Open consultation", icon=":material/open_in_new:"):
            doctor.view_consultation(linked.id)
    else:
        html('<div class="hb-card" style="font-size:.85rem;color:var(--hb-muted)">Not linked to a consultation.</div>')
    is_author = rx.provider_name == actor.user.name and rx.organization_name == actor.organization.name
    if rx.status == "issued":
        section_header("Send to pharmacy")
        if is_author:
            with st.container(key="hbform_send_rx"):
                with get_session() as s:
                    pharmacies = prescription_service.available_pharmacies(s)
                labels = {ph.id: f"{ph.name} — {ph.address.split(',')[0]}" for ph in pharmacies}
                chosen = st.selectbox("Pharmacy (chosen with the patient)", list(labels), format_func=labels.__getitem__,
                                      key="send_pharmacy")
                st.caption("The pharmacy receives only what it needs to fill the prescription — never the wider record.")
                if st.button("Send prescription", icon=":material/send:", type="primary", key="send_rx_btn"):
                    ss["rx_send_confirm"] = chosen
        else:
            alert_card("Issued", "Only the prescribing doctor at the prescribing organization can send it.", "info")
    elif rx.status != "draft" and rx.pharmacy_name:
        alert_card(f"Sent to {rx.pharmacy_name}",
                   f"Sent {fmt_datetime(rx.sent_at)}. Verification, dispensing and billing happen at the pharmacy "
                   "(Phase 3)." if rx.sent_at else "Verification and dispensing happen at the pharmacy (Phase 3).",
                   "success", "local_pharmacy")


def _dismiss_send() -> None:
    ss.pop("rx_send_confirm", None)


@st.dialog("Send prescription to pharmacy", on_dismiss=_dismiss_send)
def confirm_send(pharmacy_id: int) -> None:
    with get_session() as s:
        name = next(ph.name for ph in prescription_service.available_pharmacies(s) if ph.id == pharmacy_id)
    st.markdown(f"Send **{rx.display_id}** for **{rx.patient_name}** to **{name}**?")
    st.caption("The prescription status becomes Sent and it appears in the pharmacy's queue.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch", key="send_cancel"):
        _dismiss_send()
        st.rerun()
    if c2.button("Send to pharmacy", type="primary", width="stretch", icon=":material/send:", key="send_ok"):
        _dismiss_send()
        try:
            with get_session() as s:
                prescription_service.send_to_pharmacy(s, actor, rx.id, pharmacy_id)
            ss["hb_flash"] = f"Sent to {name}."
        except (ClinicalValidationError, AccessDenied) as exc:
            ss["hb_flash"] = f"Could not send: {exc}"
        st.rerun()


if ss.get("rx_send_confirm") and rx.status == "issued":
    confirm_send(ss["rx_send_confirm"])
