import streamlit as st

from core.db import get_session
from services import care_network_service, consent_service, record_service
from ui.components import (
    care_network_diagram,
    category_chips_html,
    consent_status_badge_html,
    empty_state,
    esc,
    html,
    lab_report_card,
    org_badge_html,
    page_header,
    phase_action,
    prescription_card,
    section_header,
    tile_html,
    timeline,
)
from ui.sections import consultations_table, medications_html, patient_hero
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)
    network = care_network_service.network(s, actor)
    consents = consent_service.list_for_patient(s, actor)

active = [c for c in consents if c.active]
first = record.patient.name.split()[0]

page_header(f"Hello, {first}", "One patient. One connected health journey — across every clinic, hospital, "
            "laboratory and pharmacy.", eyebrow="My HealthBridge")
html(f"""<div class="hb-concept">{tile_html("shield_person", "teal", 40, 22)}
  <div><div class="t">Your health records belong to your healthcare journey — you control who can access them.</div>
  <div class="s">Doctors only see what you choose to share. You can change or revoke access at any time.</div></div></div>""")
st.write("")

# --- Quick actions -----------------------------------------------------------------
with st.container(horizontal=True, gap="small"):
    if st.button("Share records with a doctor", icon=":material/person_add:", type="primary"):
        st.switch_page("views/patient/consent.py")
    phase_action("Upload a document", "upload_file", 5, key="pt_upload")
    phase_action("Add a health note", "edit_note", 5, key="pt_note")
    phase_action("Add allergy or information", "add_circle", 5, key="pt_info")
st.write("")

section_header("Health summary")
patient_hero(record)

left, right = st.columns([3, 2], gap="large")
with left:
    section_header("Recent medical activity", "Newest first · every entry shows its source")
    with st.container(key="hbcard_home_timeline"):
        timeline(record.timeline[:6])
        st.page_link("views/patient/timeline.py", label="See my full timeline", icon=":material/arrow_forward:")
    section_header("Recent healthcare encounters")
    consultations_table(record.consultations[:4], show_patient=False, empty="No visits yet")
with right:
    section_header("Current medications")
    html(f'<div class="hb-card">{medications_html([m for m in record.medications if m.current])}</div>')
    section_header("Recent prescriptions")
    if record.prescriptions:
        prescription_card(record.prescriptions[0], show_patient=False, progress=True)
    else:
        empty_state("No prescriptions yet", icon_name="prescriptions")
    section_header("Recent lab reports")
    latest = [o for o in record.reports if o.status == "published"][:1]
    for o in latest:
        lab_report_card(o, plain=True)
    if not latest:
        empty_state("No reports yet", icon_name="lab_profile")

section_header("Active consents", f"{len(active)} doctors can see your records")
if not active:
    empty_state("No one can see your records", "Share your records with a doctor when you need care.", "lock")
cols = st.columns(max(len(active), 1))
for col, c in zip(cols, active):
    with col:
        scope = "All records" if c.scope_type == "all" else category_chips_html(c.categories)
        html(f"""<div class="hb-card"><div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center">
                 <span style="font-weight:700">{esc(c.provider_name)}</span>{consent_status_badge_html(c.status)}</div>
                 <div style="margin:.35rem 0">{org_badge_html(c.organization_name, c.organization_type)}</div>
                 <div style="font-size:.8rem">{scope}</div></div>""")
st.page_link("views/patient/consent.py", label="Manage consent & access", icon=":material/shield_person:")

section_header("My Care Network", "Everyone connected to your timeline")
nodes = [(d.name, "doctor", d.specialty or "Doctor") for d in network.doctors]
nodes += [(o.organization.name, o.organization.org_type, o.relation) for o in network.organizations]
care_network_diagram(record.patient.name, nodes, len(record.timeline))
