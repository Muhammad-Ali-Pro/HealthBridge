import streamlit as st

from core.db import get_session
from services import pharmacy_service
from ui.components import badge_html, data_table, esc, fmt_when, kpi_row, org_badge_html, page_header, section_header
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    ov = pharmacy_service.queue_overview(s, actor)
    rxs = pharmacy_service.list_prescriptions(s, actor)

DISPENSE_STYLE = {
    "dispensed": ("Dispensed", "teal", "check_circle"),
    "partial": ("Partial", "amber", "hourglass_bottom"),
    "unavailable": ("Unavailable", "coral", "remove_shopping_cart"),
    "substitution_requested": ("Substitution requested", "blue", "swap_horiz"),
}

page_header("Dispensing", f"Dispensing records at {actor.organization.name} — full, partial, unavailable and "
            "substitution requests (never automatic substitution)", eyebrow="Pharmacy")
kpi_row([
    dict(label="Ready to dispense", value=ov["ready_to_dispense"], icon_name="inventory_2", tone="amber", foot="Verified"),
    dict(label="Dispensed today", value=ov["dispensed_today"], icon_name="today", tone="teal", foot="Completed handovers"),
    dict(label="Dispensed (all time)", value=ov["dispensed_total"], icon_name="local_pharmacy", tone="navy", foot=actor.organization.name),
])
st.write("")
section_header("Dispensing log")
rows = []
for rx in rxs:
    for d in rx.dispensings:
        qty = " · ".join(f"{esc(i['drug_name'])}: <b>{i.get('quantity_dispensed', '—')}</b> of {i.get('quantity_prescribed', '—')}"
                         for i in d.items)
        rows.append([
            f'<span class="strong">{esc(fmt_when(d.dispensed_at))}</span>',
            f'<span class="strong">{esc(rx.patient_name)}</span><div class="muted">{esc(rx.display_id)}</div>',
            qty,
            f'{esc(rx.provider_name)}<div style="margin-top:.25rem">{org_badge_html(rx.organization_name, rx.organization_type)}</div>',
            esc(d.pharmacist_name),
            badge_html(*DISPENSE_STYLE.get(d.status, (d.status, "neutral", None))),
        ])
data_table(["Dispensed", "Patient", "Quantity dispensed / prescribed", "Prescriber", "Pharmacist", "Status"], rows,
           empty="Nothing dispensed yet")
