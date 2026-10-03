import streamlit as st

from core.db import get_session
from services import pharmacy_service
from ui.components import allergy_chips_html, empty_state, esc, html, page_header, patient_identity_html, status_badge_html
from ui.shell import current_actor
from ui.workflows import minimum_necessary_note

actor = current_actor()
with get_session() as s:
    patients = pharmacy_service.patients(s, actor)

page_header("Patients", f"Patients with prescriptions at {actor.organization.name}", eyebrow="Pharmacy")
minimum_necessary_note(actor.organization.name)
if not patients:
    empty_state("No patients yet", icon_name="group")
cols = st.columns(3)
for i, (p, rxs) in enumerate(patients):
    allergies = rxs[0].patient_allergies
    rows = "".join(f"""<div style="display:flex;justify-content:space-between;gap:.4rem;align-items:center;padding:.4rem 0;border-top:1px solid var(--hb-border)">
        <span style="font-size:.84rem"><b>{esc(rx.display_id)}</b> · {esc(", ".join(i.drug_name for i in rx.items))}</span>{status_badge_html(rx.status)}</div>"""
                   for rx in rxs)
    with cols[i % 3]:
        html(f"""<div class="hb-card">{patient_identity_html(p)}<div style="margin:.6rem 0">{allergy_chips_html(allergies)}</div>{rows}</div>""")
