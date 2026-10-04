"""Public front page: product story + demo role selection (DEMO MODE — authentication simulated)."""

import streamlit as st

from core.models import Role
from ui import shell
from ui.components import esc, html, icon, tile_html

ROLE_CARDS = [
    (Role.PATIENT, "Patient", "person", "teal",
     ["See one timeline across every provider", "Choose who can see which records", "Send prescriptions to a pharmacy"]),
    (Role.DOCTOR, "Doctor", "stethoscope", "blue",
     ["Find patients by name or HB-ID", "View only consented records", "Consultations and e-prescriptions"]),
    (Role.PHARMACIST, "Pharmacy", "local_pharmacy", "amber",
     ["Receive e-prescriptions", "Verify and dispense", "Simulated billing"]),
    (Role.LAB, "Laboratory", "biotech", "navy",
     ["Receive test orders", "Enter and verify results", "Publish reports to the timeline"]),
]

HIDE_CHROME = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"],
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stMainBlockContainer"], .block-container { max-width: 1200px; padding-top: 1.25rem; }
.stApp { background:
  radial-gradient(1100px 520px at 85% -10%, rgba(18,145,127,.13), transparent 60%),
  radial-gradient(900px 480px at -10% 10%, rgba(240,128,96,.08), transparent 55%),
  var(--hb-mint); }
</style>"""


def render() -> None:
    st.markdown(HIDE_CHROME, unsafe_allow_html=True)
    demo = f'<span class="hb-demo inline" style="margin:0">{icon("science", 14)}{esc(shell.DEMO_LABEL)}</span>'
    logo = shell.logo_data_uri()
    html(f"""<div class="hb-landing-nav">
               <div class="brand"><img src="{logo}" alt="HealthBridge"/>
                 <span class="wordmark">Health<span>Bridge</span></span></div>
               <div class="links"><a href="#how">How it works</a><a href="#explore">Explore the demo</a>{demo}</div>
             </div>""")

    left, right = st.columns([1.15, 1], gap="large", vertical_alignment="center")
    with left:
        html(f"""
          <div class="hb-hero-l">
            <div class="hb-hero-brand"><img src="{logo}" alt=""/>
              <div><div class="wm">Health<span>Bridge</span></div>
              <div class="tag">Consent-based connected health records</div></div></div>
            <div class="hb-hero-title">One patient.<br><span>One connected health journey.</span></div>
            <div class="hb-hero-sub">Connect doctors, hospitals, laboratories and pharmacies through a secure,
              consent-based health record.</div>
            <div class="hb-hero-pills">
              <span class="hb-badge tone-teal">{icon("shield_person", 14)}Patient-controlled consent</span>
              <span class="hb-badge tone-blue">{icon("domain", 14)}Multi-organization providers</span>
              <span class="hb-badge tone-navy">{icon("history", 14)}Full audit trail</span>
            </div>
          </div>""")
    with right:
        nodes = [("stethoscope", "teal", "Dr. Arif", "South City Hospital"),
                 ("local_hospital", "blue", "City Hospital", "Hospital records"),
                 ("biotech", "navy", "HealthLab Diagnostics", "Lab reports"),
                 ("local_pharmacy", "amber", "HealthPlus Pharmacy", "Dispensing")]
        orbit = "".join(f'<div class="n">{tile_html(ic, tone, 32, 18)}<div>{esc(t)}<small>{esc(s)}</small></div></div>'
                        for ic, tone, t, s in nodes)
        html(f"""
          <div class="hb-hero-visual">
            <div class="hb-net-center" style="display:flex">{shell.avatar("Ahmed Khan")}
              <div><div class="hb-net-title">Ahmed Khan</div>
              <div class="hb-net-sub">{icon("timeline", 16)} One longitudinal timeline</div></div></div>
            <div class="hb-orbit">{orbit}</div>
            <div style="margin-top:1rem;font-size:.8rem;color:var(--hb-muted);display:flex;gap:.4rem;align-items:center">
              {icon("lock", 16)} Each provider sees only what Ahmed chooses to share.</div>
          </div>""")

    stats = [("groups", "4 roles", "Patient, doctor, pharmacy, laboratory"),
             ("domain", "8 organizations", "Clinics, hospitals, lab, pharmacies"),
             ("tune", "7 record types", "Shared selectively by the patient"),
             ("verified_user", "Every access logged", "Consent and record-access audit")]
    html('<div class="hb-stats">' + "".join(
        f'<div class="s">{tile_html(ic, "teal", 40, 22)}<div><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div></div>'
        for ic, v, l in stats) + "</div>")

    html('<div class="hb-section-title" id="explore">Explore the Demo</div>'
         '<div class="hb-section-sub">Pick a role. Every role has its own workspace and workflow.</div>')
    for col, (role, label, ic, tone, bullets) in zip(st.columns(4, gap="medium"), ROLE_CARDS):
        persona = shell.PERSONAS[role]
        with col, st.container(key=f"hbrole_{role}"):
            items = "".join(f"<li>{esc(b)}</li>" for b in bullets)
            html(f"""<div class="hb-role">{tile_html(ic, tone, 48, 26)}
                     <div class="role" style="color:var(--hb-{'teal-600' if tone == 'teal' else tone})">{esc(label)}</div>
                     <div class="who">{esc(persona.card_title)}</div><div class="org">{esc(persona.card_subtitle)}</div>
                     <ul>{items}</ul></div>""")
            st.button(f"Continue as {persona.card_title}", key=f"enter_{role}", on_click=shell.enter_as, args=(role,),
                      type="primary", width="stretch", icon=":material/arrow_forward:")
    html(f'<div style="text-align:center;margin-top:1rem">{demo}</div>')

    html('<div class="hb-section-title" id="how">How HealthBridge works</div>'
         '<div class="hb-section-sub">Records stay with the patient\'s journey — not locked inside one organization.</div>')
    steps = [("edit_note", "teal", "CREATE", "Healthcare providers create records."),
             ("hub", "blue", "CONNECT", "HealthBridge connects records into one longitudinal patient timeline."),
             ("shield_person", "violet", "CONTROL", "Patients control who can access their records.")]
    arrow = f'<div class="arrow">{icon("arrow_forward", 32)}</div>'
    cards = [f'<div class="step">{tile_html(ic, tone, 46, 24)}<div class="k">{k}</div><div class="t">{esc(t)}</div></div>'
             for ic, tone, k, t in steps]
    html(f'<div class="hb-ccc">{cards[0]}{arrow}{cards[1]}{arrow}{cards[2]}</div>')

    html(f"""<div class="hb-landing-foot"><span>{icon("health_and_safety", 16)} Synthetic demo data only. No real patients,
      authentication, payments or external integrations.</span><span>AI features (advisory, clinician-reviewed) arrive in a later phase.</span></div>""")
