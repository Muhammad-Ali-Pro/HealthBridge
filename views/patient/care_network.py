import streamlit as st

from core.db import get_session
from services import care_network_service, record_service
from ui.components import care_network_diagram, page_header, section_header
from ui.sections import care_team_doctors, care_team_organizations
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    network = care_network_service.network(s, actor)
    record = record_service.own_record(s, actor)

page_header("My Care Network", "Your doctors, clinics, hospitals, laboratories and pharmacies — all connected to one timeline.",
            eyebrow="Sharing & privacy")
nodes = [(d.name, "doctor", d.specialty or "Doctor") for d in network.doctors]
nodes += [(o.organization.name, o.organization.org_type, o.relation) for o in network.organizations]
care_network_diagram(record.patient.name, nodes, len(record.timeline))

section_header("My doctors", "Access shows what each doctor can currently see")
care_team_doctors(network)
section_header("My care organizations")
care_team_organizations(network)
st.page_link("views/patient/consent.py", label="Manage who can see my records", icon=":material/shield_person:")
