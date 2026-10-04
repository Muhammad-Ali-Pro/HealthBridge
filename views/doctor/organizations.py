import streamlit as st

from core.db import get_session
from services import provider_service
from ui.components import badge_html, card, esc, html, organization_card_html, page_header
from ui.shell import current_actor, switch_organization

actor = current_actor()
ss = st.session_state




with get_session() as s:
    orgs = provider_service.my_organizations(s, actor)

page_header("My Organizations", "Where you practise. Records you create keep the organization they were created at, "
            "and patient consent applies per organization.", eyebrow="Workspace")

cols = st.columns(min(3, len(orgs)) or 1)
for i, (m, counts) in enumerate(orgs):
    o = m.organization
    acting = o.id == actor.organization_id
    with cols[i % len(cols)], card(f"org_{o.id}", selected=acting):
        badges = (badge_html("Primary", "navy", "star") if m.is_primary else "") + \
                 (badge_html("Working here now", "teal", "radio_button_checked") if acting else "")
        html(f"""
          {organization_card_html(o.name, o.org_type, o.address)}
          <div style="margin:.8rem 0">{badges}</div>
          <div class="hb-kv"><span class="k">Your role</span><span class="v">{esc(m.title)}</span>
            <span class="k">Consultations</span><span class="v">{counts['consultations']}</span>
            <span class="k">Patients with access</span><span class="v">{counts['patients_with_access']}</span></div>""")
        if not acting:
            st.button(f"Work at {o.name}", key=f"work_{o.id}", on_click=switch_organization, args=(o.id,),
                      icon=":material/swap_horiz:", width="stretch")
