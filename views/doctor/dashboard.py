from datetime import datetime

import streamlit as st

from core.db import get_session
from services import clinical_service, dashboard_service, patient_service, provider_service, user_service
from ui import doctor
from ui.components import (
    badge_html,
    card,
    consultation_list_html,
    empty_state,
    esc,
    fmt_ago,
    fmt_time,
    fmt_when,
    html,
    kpi_row,
    org_badge_html,
    org_type_label,
    page_header,
    patient_identity_html,
    prescription_card_html,
    section_header,
    tile_html,
)
from ui.components import organization_card_html
from ui.shell import current_actor

actor = current_actor()
org = actor.organization
ss = st.session_state

with get_session() as s:
    k = dashboard_service.doctor_kpis(s, actor)
    today = provider_service.todays_consultations(s, actor)
    recent_patients = provider_service.recent_patients(s, actor)
    drafts = clinical_service.list_drafts(s, actor)
    rxs = provider_service.my_prescriptions(s, actor, include_drafts=True)
    follow_ups = provider_service.pending_follow_ups(s, actor)
    memberships = user_service.memberships(s, actor.id)
    shared = patient_service.with_access(s, actor)
    selected = next((e.patient for e in patient_service.directory(s, actor) if e.patient.id == ss.get("sel_patient")), None)
membership = next(m for m in memberships if m.organization.id == org.id)
draft_rx = [rx for rx in rxs if rx.status == "draft"]
issued_rx = [rx for rx in rxs if rx.status == "issued"][:4]

hour = datetime.now().hour
greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
page_header(f"{greeting}, {' '.join(actor.user.name.split()[:2])}",
            f"{membership.title} · {org.name} · {datetime.now():%A, %d %B %Y}", eyebrow="Clinical workspace")

html(f"""<div class="hb-concept">{tile_html("domain", "teal", 40, 22)}
  <div style="flex:1"><div class="t">Working at {esc(org.name)} ({esc(org_type_label(org.org_type))})</div>
  <div class="s">Patients grant consent to you at a specific organization. Use the “Working at” switcher in the top bar to change organization — access is re-checked immediately.</div></div></div>""")
st.write("")

# --- Quick actions ---------------------------------------------------------------------------------
with st.container(horizontal=True, gap="small"):
    if st.button("New consultation", icon=":material/add_circle:", type="primary"):
        doctor.new_consultation(ss.get("sel_patient"))
    if st.button("Find patient", icon=":material/person_search:"):
        st.switch_page(doctor.PATIENTS)
    if st.button("View timeline", icon=":material/timeline:"):
        st.switch_page("views/doctor/timeline.py")
    if st.button("Create prescription", icon=":material/prescriptions:"):
        doctor.new_prescription(ss.get("sel_patient"))
    ai_label = f"AI Clinical Copilot · {selected.name}" if selected else "AI Clinical Copilot"
    if st.button(ai_label, icon=":material/auto_awesome:"):
        if selected:
            doctor.generate_summary(selected.id)
        st.switch_page(doctor.AI_INSIGHTS)
st.write("")

kpi_row([
    dict(label="Today's consultations", value=k["consultations_today"], icon_name="stethoscope", tone="teal", foot=org.name),
    dict(label="Total patients", value=k["patients_with_access"], icon_name="group", tone="navy",
         foot=f"With active consent at {org.name}"),
    dict(label="Pending follow-ups", value=k["follow_ups"], icon_name="event_repeat", tone="blue", foot="Last 30 days"),
])
st.write("")
kpi_row([
    dict(label="Prescriptions issued", value=k["prescriptions_issued_30d"], icon_name="verified", tone="teal",
         foot=f"Last 30 days at {org.name}"),
    dict(label="AI review items", value=k["ai_review_items"], icon_name="flag", tone="violet" if k["ai_review_items"] else "neutral",
         foot="Open Copilot flags awaiting your review"),
    dict(label="Draft prescriptions", value=k["draft_prescriptions"], icon_name="edit_note", tone="amber",
         foot=f"{k['draft_consultations']} draft consultation{'s' if k['draft_consultations'] != 1 else ''}"),
])
st.write("")

left, right = st.columns([2, 1], gap="large")
with left:
    section_header("Today's consultations", f"At {org.name} · {len(today)}")
    if not today:
        empty_state("No consultations today", "Open a patient who has granted you access to start one.", "stethoscope")
    for c in today:
        status = badge_html("Draft", "amber", "edit_note") if c.status == "draft" else badge_html("Final", "teal", "verified")
        with card(f"tc_{c.id}"):
            a, b = st.columns([5, 1.2], vertical_alignment="center")
            with a:
                html(f"""<div style="display:flex;gap:.9rem;align-items:center;flex-wrap:wrap">
                  <div style="font-weight:800;font-size:1rem;min-width:4.2rem">{esc(fmt_time(c.date))}</div>
                  <div style="flex:1;min-width:180px"><div style="font-weight:700">{esc(c.patient_name)}</div>
                    <div style="font-size:.82rem;color:var(--hb-navy-600)">{esc(c.complaint or "Untitled draft")}</div></div>
                  <div>{org_badge_html(c.organization_name, c.organization_type)}</div><div>{status}</div></div>""")
            with b:
                if c.status == "draft":
                    if st.button("Continue", key=f"tc_e_{c.id}", icon=":material/edit:", width="stretch"):
                        doctor.edit_consultation(c.id, c.patient_id)
                elif st.button("Open", key=f"tc_open_{c.id}", icon=":material/open_in_new:", width="stretch"):
                    doctor.view_consultation(c.id)

    section_header("Drafts", "Private until you save or issue them")
    if not drafts and not draft_rx:
        empty_state("No drafts", icon_name="edit_note")
    for c in drafts:
        with card(f"dc_{c.id}"):
            a, b = st.columns([5, 1.2], vertical_alignment="center")
            with a:
                html(consultation_list_html(c))
            with b:
                if st.button("Continue", key=f"dc_e_{c.id}", icon=":material/edit:", type="primary", width="stretch"):
                    doctor.edit_consultation(c.id, c.patient_id)
    for rx in draft_rx:
        with card(f"drx_{rx.id}"):
            html(prescription_card_html(rx))
            if st.button("Continue draft", key=f"drx_e_{rx.id}", icon=":material/edit:", type="primary"):
                doctor.edit_prescription(rx.id, rx.patient_id)

    section_header("Recently issued prescriptions")
    if not issued_rx:
        empty_state("Nothing issued yet", icon_name="prescriptions")
    cols = st.columns(2)
    for i, rx in enumerate(issued_rx):
        with cols[i % 2], card(f"irx_{rx.id}"):
            html(prescription_card_html(rx))
            if st.button("View", key=f"irx_v_{rx.id}", icon=":material/open_in_new:"):
                doctor.view_prescription(rx.id)

with right:
    section_header("Find a patient")
    with card("dash_search"):
        q = st.text_input("Find a patient", placeholder="Name, HB-ID or phone", key="dash_q",
                          label_visibility="collapsed", icon=":material/person_search:")
        if q:
            with get_session() as s:
                hits = patient_service.directory(s, actor, q)[:4]
            if not hits:
                st.caption("No patients match.")
            for e in hits:
                html(patient_identity_html(e.patient, size=34, right=badge_html(
                    "Access" if e.access.allowed else "Restricted", "teal" if e.access.allowed else "neutral",
                    "verified_user" if e.access.allowed else "lock")))
                if st.button("Open Patient", key=f"dash_open_{e.patient.id}", width="stretch"):
                    doctor.open_patient(e.patient.id)

    section_header("Recent patients", "Where you last saw them · your access here")
    if not recent_patients:
        html('<div class="hb-card" style="font-size:.85rem;color:var(--hb-muted)">No recent patients yet.</div>')
    for r in recent_patients:
        # Two different things, labelled as such: where you last saw them vs. your access where you work now.
        access = (badge_html(f"Granted at {org.name}", "teal", "verified_user") if r.access.allowed
                  else badge_html(f"Not granted at {org.name}", "neutral", "lock"))
        with card(f"rp_{r.patient.id}"):
            html(patient_identity_html(r.patient, size=34)
                 + f"""<div style="margin-top:.55rem;font-size:.78rem;display:grid;gap:.35rem">
                   <div><div class="hb-form-section" style="margin:0 0 .15rem">Last visit</div>
                     <div style="display:flex;gap:.4rem;align-items:center;flex-wrap:wrap">{org_badge_html(r.organization_name, r.organization_type)}
                     <span style="color:var(--hb-muted)">{esc(r.activity)} · {esc(fmt_ago(r.last_interaction))}</span></div></div>
                   <div><div class="hb-form-section" style="margin:0 0 .15rem">Access</div>{access}</div></div>""")
            if st.button("Open Patient", key=f"rp_open_{r.patient.id}", width="stretch", type="tertiary"):
                doctor.open_patient(r.patient.id)

    section_header("Pending follow-ups")
    rows = "".join(f"""<div style="padding:.55rem 0;border-bottom:1px solid var(--hb-border)">
        <div style="font-weight:600;font-size:.86rem">{esc(c.patient_name)}</div>
        <div style="font-size:.8rem;color:var(--hb-navy-600)">{esc(c.follow_up)}</div>
        <div style="font-size:.74rem;color:var(--hb-muted)">Seen {esc(fmt_when(c.date))}</div></div>""" for c in follow_ups)
    html(f'<div class="hb-card" style="padding-top:.3rem">{rows}</div>' if rows else
         '<div class="hb-card" style="font-size:.85rem;color:var(--hb-muted)">No follow-ups pending.</div>')

    section_header("Shared with you", f"{len(shared)} patients")
    rows = "".join('<div style="padding:.45rem 0;border-bottom:1px solid var(--hb-border)">'
                   + patient_identity_html(e.patient, size=32, right=badge_html(
                       "All records" if e.access.scope_type == "all" else "Selected", "teal")) + "</div>"
                   for e in shared)
    html(f'<div class="hb-card" style="padding-top:.3rem">{rows}</div>' if rows else
         '<div class="hb-card" style="font-size:.85rem;color:var(--hb-muted)">No patients have shared records with you here.</div>')

    section_header("My organizations")
    for m in memberships:
        here = m.organization.id == org.id
        html(f'<div class="hb-card">{organization_card_html(m.organization.name, m.organization.org_type, m.title)}'
             f'{"<div style=margin-top:.5rem>" + badge_html("Working here now", "teal", "radio_button_checked") + "</div>" if here else ""}</div>')
