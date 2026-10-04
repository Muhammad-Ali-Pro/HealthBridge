"""Consent & Access — the patient decides who can see which records, and for how long."""

import streamlit as st

from core.db import get_session
from core.models import ConsentDuration, ConsentScopeType, RecordCategory
from core.schemas import ConsentOut
from services import audit_service, consent_service, patient_service
from ui.components import (
    CATEGORY_STYLE,
    DURATION_LABELS,
    EVENT_STYLE,
    alert_card,
    avatar_html,
    badge_html,
    card,
    category_chips_html,
    consent_card_html,
    consent_status_badge_html,
    data_table,
    empty_state,
    esc,
    fmt_datetime,
    fmt_date,
    html,
    icon,
    org_badge_html,
    page_header,
    section_header,
    tile_html,
)
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state

# Durations offered in the MVP; 24 h and 7 days are supported by the model and service too.
DURATIONS = [ConsentDuration.UNTIL_REVOKED, ConsentDuration.ONE_CONSULTATION,
             ConsentDuration.HOURS_24, ConsentDuration.DAYS_7]
CATEGORIES = [c.value for c in RecordCategory]


def scope_text(c: ConsentOut) -> str:
    return "All records" if c.scope_type == ConsentScopeType.ALL else "Selected records"


def expiry_text(c: ConsentOut) -> str:
    if c.status == "revoked" and c.revoked_at:
        return f"Revoked {fmt_datetime(c.revoked_at)}"
    if c.status == "expired":
        return "Expired"
    if c.duration == ConsentDuration.ONE_CONSULTATION:
        return "For one consultation"
    return f"Until {fmt_datetime(c.expires_at)}" if c.expires_at else "Until you revoke it"


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


def _close_dialogs() -> None:
    """Dialogs are opened through session flags so they stay open across reruns until closed."""
    for k in ("ct_share_open", "ct_revoke"):
        ss.pop(k, None)


@st.dialog("Share records with a doctor", width="large", on_dismiss=_close_dialogs)
def share_dialog() -> None:
    with get_session() as s:
        options = consent_service.search_providers(s)

    html('<div class="hb-eyebrow">Step 1 · Choose the doctor</div>')
    q = st.text_input("Search by doctor or hospital/clinic", placeholder="e.g. Arif, South City Hospital",
                      key="share_q", icon=":material/search:")
    matches = [o for o in options if not q or q.lower() in f"{o.provider_name} {o.organization_name}".lower()]
    if not matches:
        st.info("No doctors match your search.")
        return
    labels = {i: f"{o.provider_name} — {o.organization_name}" for i, o in enumerate(matches)}
    idx = st.selectbox("Doctor and organization", list(labels), format_func=labels.__getitem__, key="share_pick")
    choice = matches[idx]

    html(f"""<div class="hb-eyebrow" style="margin-top:.6rem">Step 2 · Confirm who gets access</div>
      <div class="hb-card" style="display:flex;gap:.8rem;align-items:center">{avatar_html(choice.provider_name, 44)}
        <div style="flex:1"><div style="font-weight:700">{esc(choice.provider_name)}</div>
          <div style="font-size:.8rem;color:var(--hb-muted)">{esc(choice.specialty or "Doctor")}</div></div>
        {org_badge_html(choice.organization_name, choice.organization_type)}</div>
      <div style="font-size:.8rem;color:var(--hb-muted);margin-top:.4rem">{icon("info", 14)}
        Only {esc(choice.provider_name)} at {esc(choice.organization_name)} will get access — not other doctors there,
        and not {esc(choice.provider_name)} when working at another organization.</div>""")

    html('<div class="hb-eyebrow" style="margin-top:1rem">Step 3 · What do you want to share?</div>')
    mode = st.radio("Sharing", ["selected", "all"], index=0, horizontal=True, label_visibility="collapsed",
                    format_func={"selected": "Share selected records", "all": "Share all my HealthBridge records"}.__getitem__,
                    key="share_mode")
    chosen: list[str] = []
    if mode == "selected":
        cols = st.columns(3)
        for i, cat in enumerate(CATEGORIES):
            with cols[i % 3]:
                if st.checkbox(CATEGORY_STYLE[cat][0], key=f"share_cat_{cat}"):
                    chosen.append(cat)

    html('<div class="hb-eyebrow" style="margin-top:1rem">Step 4 · For how long?</div>')
    duration = st.radio("Duration", DURATIONS, index=0, horizontal=True, label_visibility="collapsed",
                        format_func=DURATION_LABELS.__getitem__, key="share_duration")
    purpose = st.text_input("Reason (optional)", placeholder="e.g. Cardiology appointment", key="share_purpose")

    html('<div class="hb-eyebrow" style="margin-top:1rem">Step 5 · Privacy summary</div>')
    if mode == "all":
        alert_card(
            "Full medical record access",
            f"You're about to give {choice.provider_name} at {choice.organization_name} access to your complete "
            "HealthBridge medical record, including consultations, prescriptions, medications, laboratory reports, "
            "hospital records and other available health information. Only share your complete record if you are "
            "comfortable giving this provider access to all available records.", "warning", "visibility")
    elif chosen:
        hidden = [c for c in CATEGORIES if c not in chosen]
        html(f"""<div class="hb-card">
          <div style="font-size:.86rem;margin-bottom:.4rem"><b>{esc(choice.provider_name)}</b> at {esc(choice.organization_name)} will see:</div>
          {category_chips_html(chosen)}
          <div style="font-size:.86rem;margin:.6rem 0 .4rem">They will <b>not</b> see:</div>
          {category_chips_html(hidden, "neutral", locked=True) if hidden else '<span class="hb-chip tone-neutral">—</span>'}
          <div style="font-size:.8rem;color:var(--hb-muted);margin-top:.6rem">{icon("schedule", 14)} {esc(DURATION_LABELS[duration])}
            · You can revoke access at any time.</div></div>""")
    else:
        st.caption("Choose at least one type of record to share.")

    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch", key="share_cancel"):
        _close_dialogs()
        st.rerun()
    label = "Confirm & Share All Records" if mode == "all" else "Share selected records"
    if c2.button(label, type="primary", width="stretch", disabled=mode == "selected" and not chosen, key="share_confirm"):
        with get_session() as s:
            consent = consent_service.grant(
                s, actor, provider_id=choice.provider_id, organization_id=choice.organization_id,
                scope_type=ConsentScopeType.ALL if mode == "all" else ConsentScopeType.SELECTED,
                categories=chosen, duration=duration, purpose=purpose, confirm_all=mode == "all")
        ss["consent_success"] = consent.model_dump(mode="json")
        for k in [k for k in ss if k.startswith("share_")]:
            del ss[k]
        _close_dialogs()
        st.rerun()


@st.dialog("Revoke access", on_dismiss=_close_dialogs)
def revoke_dialog(c: ConsentOut) -> None:
    html(f"""<div style="display:flex;gap:.8rem;align-items:center;margin-bottom:.8rem">{avatar_html(c.provider_name, 44)}
      <div><div style="font-weight:700">{esc(c.provider_name)}</div>{org_badge_html(c.organization_name, c.organization_type)}</div></div>""")
    st.write(f"{c.provider_name} will no longer be able to open your HealthBridge records at {c.organization_name}.")
    st.caption("Your medical records are not deleted — revoking only removes this doctor's access. "
               "The change is recorded in your access history.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch", key=f"rv_cancel_{c.id}"):
        _close_dialogs()
        st.rerun()
    if c2.button("Revoke access", type="primary", width="stretch", key=f"rv_ok_{c.id}"):
        with get_session() as s:
            consent_service.revoke(s, actor, c.id)
        ss["hb_flash"] = f"Access revoked for {c.provider_name} at {c.organization_name}."
        _close_dialogs()
        st.rerun()


@st.dialog("Access details", width="large")
def details_dialog(c: ConsentOut, history) -> None:
    scope = (badge_html("All records", "teal", "select_all") if c.scope_type == "all" else category_chips_html(c.categories))
    html(f"""
      <div style="display:flex;gap:.8rem;align-items:center;margin-bottom:1rem">{avatar_html(c.provider_name, 48)}
        <div style="flex:1"><div style="font-weight:700;font-size:1.05rem">{esc(c.provider_name)}</div>
          {org_badge_html(c.organization_name, c.organization_type)}</div>{consent_status_badge_html(c.status)}</div>
      <div class="hb-kv">
        <span class="k">Consent ID</span><span class="v">{esc(c.display_id)}</span>
        <span class="k">Access</span><span class="v">{esc(scope_text(c))}</span>
        <span class="k">Shared</span><span class="v">{scope}</span>
        <span class="k">Granted</span><span class="v">{esc(fmt_datetime(c.granted_at))}</span>
        <span class="k">Duration</span><span class="v">{esc(DURATION_LABELS.get(c.duration, c.duration))} · {esc(expiry_text(c))}</span>
        <span class="k">Reason</span><span class="v">{esc(c.purpose or "—")}</span>
      </div>""")
    section_header("When they opened your record")
    rows = [[f'<span class="strong">{esc(fmt_datetime(e.timestamp))}</span>', esc(e.resource_type.replace("_", " ").title())]
            for e in history if e.action == "RECORD_ACCESSED" and e.provider_name == c.provider_name
            and e.organization_name == c.organization_name]
    data_table(["When", "What they viewed"], rows, empty="Not opened yet")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

with get_session() as s:
    consents = consent_service.list_for_patient(s, actor)
    me = patient_service.own_identity(s, actor)
    history = audit_service.patient_history(s, actor, me.id)
    activity = audit_service.patient_history(s, actor, me.id, include_activity=True)

active = [c for c in consents if c.active]
past = [c for c in consents if not c.active]

head, action = st.columns([3, 1.3], vertical_alignment="bottom")
with head:
    page_header("Consent & Access", "You decide which doctors can see your HealthBridge records — and exactly what they see.",
                eyebrow="Sharing & privacy")
with action, st.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Share Records with a Doctor", icon=":material/add:", type="primary", key="open_share"):
        ss["ct_share_open"] = True

done = ss.pop("consent_success", None)
if done:
    alert_card(f"Access granted to {done['provider_name']}",
               f"{done['organization_name']} · {'All records' if done['scope_type'] == 'all' else 'Selected records'} · "
               f"Consent ID CON-{done['id']:06d}. You can revoke this at any time.", "success")

html(f"""<div class="hb-concept">{tile_html("lock_person", "teal", 40, 22)}
  <div><div class="t">Consent is specific to one doctor at one organization.</div>
  <div class="s">Sharing with Dr. Ayesha at Clifton Family Clinic does not give access to other doctors there,
  or to Dr. Ayesha at another hospital. Revoking never deletes your records.</div></div></div>""")
st.write("")

section_header("People with access", f"{len(active)} active")
if not active:
    empty_state("No one can see your records", "Use “Share Records with a Doctor” when you visit a new doctor.", "lock")
cols = st.columns(2)
for i, c in enumerate(active):
    with cols[i % 2], card(f"consent_{c.id}"):
        html(consent_card_html(c, meta=f"Granted {esc(fmt_date(c.granted_at))} · {esc(expiry_text(c))} · {esc(c.display_id)}"))
        b1, b2 = st.columns(2)
        if b1.button("View access", key=f"det_{c.id}", icon=":material/visibility:", width="stretch"):
            details_dialog(c, history)
        if b2.button("Revoke access", key=f"rev_{c.id}", icon=":material/block:", width="stretch"):
            ss["ct_revoke"] = c.id

if past:
    section_header("Past access", "Revoked or expired — records were never deleted")
    data_table(["Doctor", "Organization", "Access", "Status", "Granted", "Ended"], [[
        f'<span class="strong">{esc(c.provider_name)}</span>', org_badge_html(c.organization_name, c.organization_type),
        esc(scope_text(c)), consent_status_badge_html(c.status), esc(fmt_date(c.granted_at)), esc(expiry_text(c)),
    ] for c in past])

section_header("History", "Every consent change, every time a doctor opened your record, and all record activity")
ACTION_STYLE = {
    "CONSENT_GRANTED": ("Consent granted", "teal", "add_moderator"),
    "CONSENT_REVOKED": ("Consent revoked", "neutral", "remove_moderator"),
    "RECORD_ACCESSED": ("Record opened", "blue", "visibility"),
    "ACCESS_DENIED": ("Access blocked", "coral", "block"),
    "AI_SUMMARY_GENERATED": ("AI summary generated", "violet", "auto_awesome"),
}


def scope_cell(e) -> str:
    d = e.details or {}
    cats = d.get("categories") if "categories" in d else d.get("scope")
    if cats == "all" or d.get("all_records"):
        return badge_html("All records", "neutral")
    return category_chips_html(cats or [], "neutral") if isinstance(cats, list) else "—"


def event_badge(e) -> str:
    if e.action == "CONSENT_REVOKED" and "superseded" in (e.details or {}).get("reason", ""):
        return badge_html("Consent replaced", "neutral", "swap_horiz")
    return badge_html(*ACTION_STYLE.get(e.action, (e.action, "neutral", "info")))


tab_access, tab_activity = st.tabs([f"Consent & access ({len(history)})", f"All record activity ({len(activity)})"])
with tab_access:
    data_table(["Event", "Doctor", "Organization", "Scope", "When"], [[
        event_badge(e),
        esc(e.provider_name or "—"),
        esc(e.organization_name or "—"),
        scope_cell(e) + (f'<div class="muted">{esc(e.resource_type.replace("_", " "))}</div>' if e.action == "RECORD_ACCESSED" else ""),
        f'<span class="muted">{esc(fmt_datetime(e.timestamp))}</span>',
    ] for e in history], empty="No access activity yet")
with tab_activity:
    data_table(["Activity", "By", "Organization", "Details", "When"], [[
        event_badge(e) if e.action in ACTION_STYLE else badge_html(
            EVENT_STYLE.get((e.details or {}).get("event", ""), ("Record created",))[0], "navy", "history_edu"),
        esc(e.actor_name or "—"),
        esc(e.organization_name or ("You" if e.actor_type == "patient" else "—")),
        esc((e.details or {}).get("summary", "")) or scope_cell(e),
        f'<span class="muted">{esc(fmt_datetime(e.timestamp))}</span>',
    ] for e in activity], empty="No activity yet")

if ss.get("ct_share_open"):
    share_dialog()
elif ss.get("ct_revoke"):
    target = next((c for c in active if c.id == ss["ct_revoke"]), None)
    if target:
        revoke_dialog(target)
    else:
        _close_dialogs()
