import streamlit as st

from core.db import get_session
from services import lab_service
from ui.components import empty_state, esc, html, icon, lab_status_badge_html, page_header, patient_identity_html
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    patients = lab_service.patients(s, actor)

page_header("Patients", f"Patients with test orders at {actor.organization.name}", eyebrow="Laboratory")
html(f"""<div class="hb-plain" style="margin:0 0 1rem">{icon("shield_lock", 16)}
  The laboratory sees only the tests ordered from it — never the patient's wider HealthBridge record.</div>""")
if not patients:
    empty_state("No patients yet", icon_name="group")
cols = st.columns(3)
for i, (p, orders) in enumerate(patients):
    rows = "".join(f"""<div style="display:flex;justify-content:space-between;gap:.4rem;align-items:center;padding:.4rem 0;border-top:1px solid var(--hb-border)">
        <span style="font-size:.84rem"><b>{esc(o.test_name)}</b><br><span style="color:var(--hb-muted);font-size:.76rem">{esc(o.provider_name)} · {esc(o.organization_name)}</span></span>
        {lab_status_badge_html(o.status)}</div>""" for o in orders)
    with cols[i % 3]:
        html(f'<div class="hb-card">{patient_identity_html(p)}<div style="margin-top:.6rem">{rows}</div></div>')
