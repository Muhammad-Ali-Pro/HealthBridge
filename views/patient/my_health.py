import streamlit as st

from core.db import get_session
from services import record_service
from ui.components import (
    FLAG_LABEL,
    badge_html,
    document_card_html,
    empty_state,
    esc,
    fmt_date,
    html,
    page_header,
    patient_entry_html,
    patient_provided_badge_html,
    phase_action,
    section_header,
)
from ui.sections import consultation_card, medications_html, patient_hero
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)

page_header("My Health", "A simple summary of your health, gathered from all your providers — plus what you add yourself.",
            eyebrow="My HealthBridge")
patient_hero(record)

left, right = st.columns(2, gap="large")
with left:
    section_header("Medicines I'm taking now")
    html(f'<div class="hb-card">{medications_html([m for m in record.medications if m.current])}</div>')
    section_header("My last visit")
    if record.consultations:
        consultation_card(record.consultations[0], title="Last visit")
    else:
        empty_state("No visits yet", icon_name="stethoscope")
with right:
    section_header("My latest test results", "In plain language")
    published = [o for o in record.reports if o.status == "published"]
    if not published:
        empty_state("No results yet", icon_name="lab_profile")
    for o in published[:1]:
        rows = "".join(f"""
          <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center;padding:.5rem 0;border-bottom:1px solid var(--hb-border)">
            <div><div style="font-weight:600;font-size:.88rem">{esc(v.analyte)}</div>
              <div style="font-size:.76rem;color:var(--hb-muted)">Normal range {esc(v.reference)} {esc(v.unit)}</div></div>
            <div style="text-align:right"><div style="font-weight:800">{esc(v.value)} <span style="font-weight:500;font-size:.78rem;color:var(--hb-muted)">{esc(v.unit)}</span></div>
              {badge_html(*FLAG_LABEL.get(v.flag, (v.flag, "neutral")))}</div>
          </div>""" for v in o.values)
        html(f"""<div class="hb-card"><div class="hb-section" style="margin-top:0"><h3>{esc(o.test_name)}</h3>
                 <span class="hint">{esc(o.lab_name)} · {esc(fmt_date(o.published_at or o.ordered_at))}</span></div>{rows}
                 <div style="font-size:.8rem;color:var(--hb-muted);margin-top:.6rem">Talk to your doctor about what these results mean for you.</div></div>""")

section_header("Information I added", "Clearly marked as patient-provided")
with st.container(horizontal=True, gap="small"):
    phase_action("Add a health note", "edit_note", 5, key="mh_note")
    phase_action("Add allergy or information", "add_circle", 5, key="mh_info")
entries = "".join(patient_entry_html(e) for e in record.patient_entries)
html(f'<div class="hb-card" style="padding-top:.4rem">{entries}</div>' if entries
     else f'<div class="hb-card">{patient_provided_badge_html()} Nothing added yet.</div>')

section_header("My documents", "Uploaded by you or by your providers")
with st.container(horizontal=True, gap="small"):
    phase_action("Upload a document", "upload_file", 5, key="mh_upload")
cols = st.columns(3)
for i, d in enumerate(record.documents):
    with cols[i % 3]:
        html(f'<div class="hb-card">{document_card_html(d)}</div>')
if not record.documents:
    empty_state("No documents yet", icon_name="description")
