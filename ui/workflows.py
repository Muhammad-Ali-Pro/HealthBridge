"""Master-detail queues for the pharmacy and laboratory workspaces."""

from collections.abc import Callable, Sequence

import streamlit as st

from core.models import LabOrderStatus, PrescriptionStatus
from core.schemas import LabOrderOut, PrescriptionOut
from ui.components import (
    alert_card,
    allergy_chips_html,
    badge_html,
    card,
    data_table,
    empty_state,
    esc,
    fmt_when,
    html,
    icon,
    lab_report_card_html,
    lab_status_badge_html,
    lab_values_table_html,
    invoice_items_html,
    org_badge_html,
    patient_meta,
    payment_badge_html,
    phase_action,
    section_header,
    status_badge_html,
)


def master_detail(key: str, rows: Sequence, card_html: Callable, detail: Callable, empty: str) -> None:
    if not rows:
        empty_state(empty, "New items will appear here automatically.", "inbox")
        return
    sel_key = f"sel_{key}"
    ids = [r.id for r in rows]
    if st.session_state.get(sel_key) not in ids:
        st.session_state[sel_key] = ids[0]
    left, right = st.columns([1, 1.7], gap="large")
    with left:
        for r in rows:
            chosen = r.id == st.session_state[sel_key]
            with card(f"q_{key}_{r.id}", selected=chosen):
                html(card_html(r))
                st.button("Review", key=f"rv_{key}_{r.id}", icon=":material/open_in_new:", width="stretch",
                          on_click=st.session_state.__setitem__, args=(sel_key, r.id),
                          type="primary" if chosen else "secondary")
    with right:
        detail(next(r for r in rows if r.id == st.session_state[sel_key]))


def minimum_necessary_note(org_name: str) -> None:
    html(f"""<div class="hb-plain" style="margin:0 0 1rem">{icon("shield_lock", 16)}
      Minimum necessary access: {esc(org_name)} sees only the prescriptions sent to it — patient identity, allergies,
      prescriber, organization, medicines and instructions. Diagnoses and the wider medical record are not shared.</div>""")


def pharmacy_detail(rx: PrescriptionOut) -> None:
    with card(f"rxd_{rx.id}"):
        html(f"""
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;flex-wrap:wrap">
            <div><div class="hb-eyebrow">Prescription {esc(rx.display_id)}</div>
              <div style="font-size:1.25rem;font-weight:800;letter-spacing:-.02em">{esc(rx.patient_name)}</div>
              <div style="font-size:.82rem;color:var(--hb-muted)">{rx.patient_age} yrs · {esc(rx.patient_sex.title())} · received {esc(fmt_when(rx.created_at))}</div></div>
            {status_badge_html(rx.status)}
          </div>
          <div style="margin-top:.8rem">{allergy_chips_html(rx.patient_allergies)}</div>""")
        section_header("Medication")
        data_table(["Medicine", "Strength", "Dosage", "Route", "Frequency", "Duration", "Qty"], [[
            f'<span class="strong">{esc(i.drug_name)}</span><div class="muted">{esc(i.instructions)}</div>',
            esc(i.strength), esc(i.dosage or "—"), esc(i.route), esc(i.frequency), f"{i.duration_days} days", str(i.quantity),
        ] for i in rx.items])
        html(f"""
          <div class="hb-kv" style="margin:.4rem 0 1rem">
            <span class="k">Prescriber</span><span class="v">{esc(rx.provider_name)}</span>
            <span class="k">Prescribed at</span><span class="v">{org_badge_html(rx.organization_name, rx.organization_type)}</span>
            <span class="k">Dispensing at</span><span class="v">{esc(rx.pharmacy_name or "—")}</span>
          </div>""")
        section_header("Verification checklist", "Pharmacist confirms each item")
        html("".join(f'<div style="display:flex;gap:.5rem;align-items:center;font-size:.86rem;margin-bottom:.4rem">'
                     f'{icon("check_box_outline_blank", 18)}{esc(c)}</div>' for c in
                     ["Patient identity", "Allergy cross-check", "Dose, frequency and duration", "Prescriber and organization"]))
        if rx.invoice:
            section_header("Billing", rx.invoice.invoice_number)
            html(f'<div class="hb-table-wrap">{invoice_items_html(rx.invoice)}</div>'
                 f'<div style="margin-top:.5rem">{payment_badge_html(rx.invoice.payment_status)}</div>')
        alert_card("AI pharmacy check", "Structure and discrepancy checks arrive in Phase 6. They flag issues for you to "
                   "review — they never approve, substitute or change a prescription.", "ai")
        with st.container(horizontal=True):
            if rx.status == PrescriptionStatus.SENT:
                phase_action("Verify prescription", "verified", 3, key=f"verify_{rx.id}", primary=True)
                phase_action("Reject with reason", "block", 3, key=f"reject_{rx.id}")
            elif rx.status in (PrescriptionStatus.VERIFIED, PrescriptionStatus.PARTIALLY_DISPENSED):
                phase_action("Record dispensing", "local_pharmacy", 3, key=f"dispense_{rx.id}", primary=True)
                phase_action("Partial dispensing", "hourglass_bottom", 3, key=f"partial_{rx.id}")
                phase_action("Medicine unavailable", "remove_shopping_cart", 3, key=f"unavail_{rx.id}")
                phase_action("Request substitution", "swap_horiz", 3, key=f"subst_{rx.id}")
            elif rx.status == PrescriptionStatus.DISPENSED and not rx.invoice:
                phase_action("Generate invoice", "receipt_long", 3, key=f"invoice_{rx.id}", primary=True)


def lab_order_card_html(o: LabOrderOut) -> str:
    prio = badge_html("Urgent", "coral", "priority_high") if o.priority == "urgent" else ""
    return f"""
      <div class="hb-rx">
        <div class="head"><div class="title">{esc(o.patient.name)}</div><span>{prio} {lab_status_badge_html(o.status)}</span></div>
        <div class="sub">{esc(o.display_id)} · {esc(o.test_name)}</div>
        <div style="margin-top:.45rem">{org_badge_html(o.organization_name, o.organization_type)}</div>
        <div class="foot"><span>{icon("person", 14)} {esc(o.provider_name)}</span><span>{icon("schedule", 14)} {esc(fmt_when(o.ordered_at))}</span></div>
      </div>"""


def lab_detail(o: LabOrderOut) -> None:
    with card(f"labd_{o.id}"):
        prio = badge_html("Urgent", "coral", "priority_high") if o.priority == "urgent" else badge_html("Routine", "neutral")
        html(f"""
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;flex-wrap:wrap">
            <div><div class="hb-eyebrow">Test order {esc(o.display_id)}</div>
              <div style="font-size:1.25rem;font-weight:800;letter-spacing:-.02em">{esc(o.test_name)}</div>
              <div style="font-size:.82rem;color:var(--hb-muted)">{esc(o.patient.name)} · {esc(patient_meta(o.patient))}</div></div>
            <span>{prio} {lab_status_badge_html(o.status)}</span>
          </div>
          <div class="hb-kv" style="margin:1rem 0">
            <span class="k">Ordered by</span><span class="v">{esc(o.provider_name)}</span>
            <span class="k">Ordering org</span><span class="v">{org_badge_html(o.organization_name, o.organization_type)}</span>
            <span class="k">Ordered</span><span class="v">{esc(fmt_when(o.ordered_at))}</span>
            <span class="k">Type</span><span class="v">{esc(o.test_category.title())}</span>
            <span class="k">Clinical notes</span><span class="v">{esc(o.clinical_notes or "—")}</span>
          </div>""")
        if o.values:
            section_header("Results", "Entered by the laboratory")
            html(lab_values_table_html(o))
            if o.interpretation:
                html(f'<div style="font-size:.86rem;margin-top:.6rem"><b>Interpretation:</b> {esc(o.interpretation)}</div>')
            if o.lab_notes:
                html(f'<div style="font-size:.86rem;margin-top:.3rem"><b>Lab notes:</b> {esc(o.lab_notes)}</div>')
        alert_card("Minimum necessary", "The laboratory sees the patient's identity and this test order only — "
                   "never consultations, prescriptions or the wider record. Labs cannot edit doctors' records.", "lock")
        with st.container(horizontal=True):
            if o.status == LabOrderStatus.ORDERED:
                phase_action("Mark sample received", "science", 4, key=f"recv_{o.id}", primary=True)
            elif o.status == LabOrderStatus.RECEIVED:
                phase_action("Enter results", "edit_note", 4, key=f"enter_{o.id}", primary=True)
            elif o.status == LabOrderStatus.RESULTED:
                phase_action("Verify results", "fact_check", 4, key=f"verify_{o.id}", primary=True)
            elif o.status == LabOrderStatus.VERIFIED:
                phase_action("Publish report to patient timeline", "publish", 4, key=f"publish_{o.id}", primary=True)
            if o.status != LabOrderStatus.PUBLISHED:
                phase_action("Add lab note", "note_add", 4, key=f"labnote_{o.id}")
                phase_action("Attach document", "attach_file", 4, key=f"labdoc_{o.id}")


def lab_report_html(o: LabOrderOut) -> str:
    return lab_report_card_html(o, show_patient=True)
