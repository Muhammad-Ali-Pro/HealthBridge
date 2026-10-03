import streamlit as st

from core.db import get_session
from services import clinical_service, provider_service
from ui import doctor
from ui.components import card, consultation_list_html, empty_state, html, kpi_row, page_header
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state

with get_session() as s:
    allc = provider_service.my_consultations(s, actor)
    drafts = clinical_service.list_drafts(s, actor)
    follow_ups = provider_service.pending_follow_ups(s, actor)

head, actions = st.columns([3, 1], vertical_alignment="bottom")
with head:
    page_header("Consultations", "Consultations you recorded — each kept with its organization context.", eyebrow="Clinical")
with actions, st.container(horizontal=True, horizontal_alignment="right"):
    if st.button("New consultation", icon=":material/add:", type="primary"):
        doctor.new_consultation(ss.get("sel_patient"))

today = provider_service.start_of_today()
kpi_row([
    dict(label="Today", value=sum(c.date >= today for c in allc if c.organization_name == actor.organization.name),
         icon_name="today", tone="teal", foot=actor.organization.name),
    dict(label="Drafts", value=len(drafts), icon_name="edit_note", tone="amber", foot="Private until saved"),
    dict(label="Follow-ups (30 days)", value=len(follow_ups), icon_name="event_repeat", tone="blue", foot="With follow-up instructions"),
    dict(label="All time", value=len(allc), icon_name="stethoscope", tone="navy", foot="Across your organizations"),
])
st.write("")


def rows(items, key: str, empty: str) -> None:
    if not items:
        empty_state(empty, icon_name="stethoscope")
    for c in items:
        with card(f"{key}_{c.id}"):
            left, right = st.columns([5, 1.2], vertical_alignment="center")
            with left:
                html(consultation_list_html(c))
            with right:
                if c.status == "draft":
                    if st.button("Continue", key=f"{key}_e_{c.id}", icon=":material/edit:", type="primary", width="stretch"):
                        doctor.edit_consultation(c.id, c.patient_id)
                elif st.button("Open", key=f"{key}_o_{c.id}", icon=":material/open_in_new:", width="stretch"):
                    doctor.view_consultation(c.id)


here = [c for c in allc if c.organization_name == actor.organization.name]
t_today, t_drafts, t_here, t_all = st.tabs([
    f"Today ({sum(c.date >= today for c in here)})", f"Drafts ({len(drafts)})",
    f"At {actor.organization.name} ({len(here)})", f"All organizations ({len(allc)})"])
with t_today:
    rows([c for c in here if c.date >= today], "t", "No consultations recorded today")
with t_drafts:
    rows(drafts, "d", "No drafts")
with t_here:
    rows(here, "h", "No consultations here yet")
with t_all:
    rows(allc, "a", "No consultations yet")
