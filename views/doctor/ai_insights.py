import streamlit as st

from core.db import get_session
from services import patient_service
from ui import copilot_view, doctor
from ui.components import empty_state, page_header
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state

page_header("AI Clinical Copilot", "Multi-agent summary of a patient's authorized record, with flags for your review. "
            "It never diagnoses, prescribes or changes records.", eyebrow="AI Insights")

with get_session() as s:
    shared = patient_service.with_access(s, actor)
entries = {e.patient.id: e for e in shared}

if not shared:
    empty_state("Select a patient to generate an AI clinical summary.",
                f"No patients have granted you access at {actor.organization.name} yet.", "auto_awesome", tone="violet")
    st.stop()

ids = list(entries)
pick_col, _ = st.columns([1.4, 2])
with pick_col:
    pid = st.selectbox("Patient", ids, index=ids.index(ss["sel_patient"]) if ss.get("sel_patient") in ids else None,
                       placeholder="Select a patient", key="ai_patient",
                       format_func=lambda i: f"{entries[i].patient.name}  ·  {entries[i].patient.display_id}")
if pid is None:
    empty_state("Select a patient to generate an AI clinical summary.",
                "Only patients who granted you access here are listed.", "auto_awesome", tone="violet")
    st.stop()
ss["sel_patient"] = pid

entry = entries[pid]
doctor.consent_banner(actor, entry.access, entry.patient.name)
st.write("")
copilot_view.panel(actor, pid, entry.patient.name, key="aiins", autorun=ss.pop("copilot_autorun", False))
