import time

import streamlit as st

from agents import llm as llm_module
from core.db import get_session
from services import copilot_service, patient_service
from services.access_service import AccessDenied
from ui import copilot_view, doctor
from ui.components import alert_card, badge_html, empty_state, esc, html, icon, page_header, tile_html
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state

page_header("AI Insights", "HealthBridge Clinical Copilot — organizes and summarizes a patient's authorized record for "
            "your review. It never diagnoses, prescribes or changes records.", eyebrow="Clinical Copilot")

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
if pid != ss.get("sel_patient"):
    ss["sel_patient"] = pid

entry = entries[pid]
doctor.consent_banner(actor, entry.access, entry.patient.name)
st.write("")

mode = (badge_html("OpenAI connected", "violet", "auto_awesome") if llm_module.available()
        else badge_html("AI not configured — rule-based fallback", "neutral", "rule"))
html(f"""<div class="hb-card" style="display:flex;gap:1rem;align-items:center;flex-wrap:wrap">{tile_html("auto_awesome", "violet", 44, 24)}
  <div style="flex:1;min-width:240px"><div style="font-weight:700">Generate a clinical summary for {esc(entry.patient.name)}</div>
  <div style="font-size:.82rem;color:var(--hb-muted)">Consent check → authorized records → record organizer → Clinical Summary Agent →
  Consistency Review Agent → your review</div></div>{mode}</div>""")

autorun = ss.pop("copilot_autorun", False)
clicked = st.button("Generate Clinical Summary", icon=":material/auto_awesome:", type="primary")

result = None
if clicked or autorun:
    with st.status("Reviewing authorized records…", expanded=True) as status:
        def progress(message: str) -> None:
            status.update(label=message)
            st.write(f"{message}")
            time.sleep(0.25)  # keep each agent step visible during the demo
        try:
            with get_session() as s:
                result = copilot_service.generate(s, actor, pid, on_progress=progress)
            status.update(label="Summary ready for clinician review", state="complete", expanded=False)
        except AccessDenied as exc:
            status.update(label="Access denied", state="error")
            alert_card("Access denied", str(exc), "danger")
        except Exception:  # never let AI problems break the clinical workflow
            status.update(label="AI summary is temporarily unavailable.", state="error")
            alert_card("AI summary is temporarily unavailable.", "You can continue using HealthBridge normally.", "warning")
else:
    try:
        with get_session() as s:
            result = copilot_service.latest(s, actor, pid)
    except AccessDenied:
        result = None
    if result:
        html(f'<div style="font-size:.8rem;color:var(--hb-muted);margin:.4rem 0">{icon("history", 14)} '
             'Showing your most recent summary for this patient. Generate again to refresh.</div>')

if result:
    copilot_view.render(result)
