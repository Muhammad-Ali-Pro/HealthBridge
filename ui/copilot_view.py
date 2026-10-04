"""AI Clinical Copilot panel: generate, agent progress, summary, flags (accept / dismiss / view source)."""

import time

import streamlit as st

from agents.schemas import DISCLAIMER, NOT_DOCUMENTED, CopilotResult
from core.db import get_session
from core.schemas import Actor
from services import copilot_service
from services.access_service import AccessDenied
from ui import ai_settings
from ui.components import (
    alert_card,
    badge_html,
    card,
    esc,
    fmt_datetime,
    html,
    icon,
    org_badge_html,
    tile_html,
)

SEVERITY = {"high": ("High", "coral"), "medium": ("Medium", "amber"), "low": ("Low", "blue")}
FLAG_STATUS = {"open": ("Awaiting your review", "blue", "schedule"), "accepted": ("Accepted", "teal", "check_circle"),
               "dismissed": ("Dismissed", "neutral", "do_not_disturb_on")}
RETRIEVAL_LABELS = {"consultations": "Consultations", "clinical_notes": "Clinical notes", "prescriptions": "Prescriptions",
                    "medications": "Current medications", "labs": "Lab reports", "documents": "Documents",
                    "patient_provided": "Patient-provided"}
ss = st.session_state


def _cites(ids: list[str], labels: dict[str, str]) -> str:
    return "".join(f'<span class="hb-cite" title="{esc(labels.get(i, i))}">{esc(i)}</span>' for i in ids)


def _section(title: str, ic: str, body: str) -> None:
    html(f'<div class="hb-ai-out" style="margin-bottom:.8rem"><div class="hb-ai-h"><h4>{icon(ic, 18)} {esc(title)}</h4></div>{body}</div>')


def _items(items, labels) -> str:
    if not items:
        return f'<div class="hb-ai-item" style="color:var(--hb-muted)">{esc(NOT_DOCUMENTED)}</div>'
    return "".join(f'<div class="hb-ai-item">{esc(i.text)}<div>{_cites(i.sources, labels)}</div></div>' for i in items)


@st.dialog("View source", width="large")
def _source_dialog(actor: Actor, patient_id: int, source_ids: list[str]) -> None:
    st.caption("Each cited record is re-read through the consent service — exactly what you are authorized to see.")
    with get_session() as s:
        details = copilot_service.resolve_sources(s, actor, patient_id, source_ids)
    for d in details:
        org = org_badge_html(d.organization_name, d.organization_type) if d.organization_name else ""
        state = "" if d.available else badge_html("Not available", "neutral", "lock")
        html(f"""<div class="hb-card" style="margin-bottom:.6rem">
          <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center;flex-wrap:wrap">
            <span><span class="hb-cite">{esc(d.id)}</span> <b>{esc(d.record_type)}</b></span>{state}</div>
          <div class="hb-kv" style="margin-top:.6rem">
            <span class="k">Record</span><span class="v">{esc(d.title)}</span>
            <span class="k">Date</span><span class="v">{esc(fmt_datetime(d.date)) if d.date else "—"}</span>
            <span class="k">Organization</span><span class="v">{org or "—"}</span>
            <span class="k">Doctor / author</span><span class="v">{esc(d.provider_name or "—")}</span>
            <span class="k">Record ID</span><span class="v">{esc(d.id)}</span>
            <span class="k">Content</span><span class="v">{esc(d.excerpt) or "—"}</span></div></div>""")


def _review(actor: Actor, flag_id: int, decision: str) -> None:
    with get_session() as s:
        copilot_service.review_flag(s, actor, flag_id, decision)
    ss["hb_flash"] = "Flag accepted for follow-up." if decision == "accepted" else "Flag dismissed."


def render(actor: Actor, patient_id: int, result: CopilotResult, key: str) -> None:
    labels = {s.id: f"{s.label} {s.date}".strip() for s in result.sources}
    total = sum(result.retrieval.values()) if result.retrieval else sum(result.record_counts.values())
    with get_session() as s:
        flags = copilot_service.flags_for_summary(s, actor, result.summary_id) if result.summary_id else {}
    sm = result.summary
    if result.generator == "llm":
        generator = (badge_html("AI-generated — clinician verification required", "violet", "auto_awesome")
                     + f'<div style="font-size:.74rem;color:var(--hb-muted);margin-top:.25rem">{esc(result.provider or "")}'
                       f' · {esc(result.model or "")}</div>')
    else:  # never present the deterministic fallback as live model output
        generator = (badge_html("Demo AI response — live model unavailable", "amber", "science")
                     + '<div style="font-size:.74rem;color:var(--hb-muted);margin-top:.25rem">Deterministic rules · '
                       'clinician verification required</div>')
    open_n = sum(f.status == "open" for f in flags.values())
    html(f"""<div class="hb-card" style="display:flex;gap:1.2rem;flex-wrap:wrap;align-items:center;justify-content:space-between">
      <div><div class="hb-form-section">{total} authorized record{'s' if total != 1 else ''} analyzed</div><b>Based on {total} consented record{'s' if total != 1 else ''}.</b></div>
      <div><div class="hb-form-section">Requested by</div>{esc(result.provider_name)} · {esc(result.organization_name)}</div>
      <div><div class="hb-form-section">Generated</div>{esc(fmt_datetime(result.generated_at))}</div>
      <div>{generator}</div></div>""")
    for n in result.notices:
        alert_card(n, tone="warning", icon_name="info")
    if result.removed_unsupported:
        alert_card(f"{result.removed_unsupported} AI statement(s) without a verifiable source were removed.", tone="info",
                   icon_name="fact_check")

    left, right = st.columns([3, 2], gap="large")
    with left:
        html('<div class="hb-section"><h3>Clinical Summary</h3></div>')
        _section("Recent clinical history", "history", _items(sm.recent_history, labels))
        meds = ("".join(f"""<div class="hb-ai-item"><b>{esc(m.medicine)}</b> — {esc(m.strength)} · {esc(m.dosage)} · {esc(m.frequency)}
                   <div style="font-size:.76rem;color:var(--hb-muted)">Since {esc(m.date)}</div><div>{_cites(m.sources, labels)}</div></div>"""
                        for m in sm.current_medications)
                or f'<div class="hb-ai-item" style="color:var(--hb-muted)">{esc(NOT_DOCUMENTED)}</div>')
        _section("Current medications", "medication", meds)
        _section("Recent prescriptions", "prescriptions", _items(sm.recent_prescriptions, labels))
        _section("Recent changes", "change_circle", _items(sm.important_changes, labels))
        _section("Follow-up information", "event_repeat", _items(sm.follow_up, labels))
        _section("Active conditions (as documented)", "monitor_heart", _items(sm.active_conditions, labels))
        if "lab_reports" in result.authorized_categories or "imaging_reports" in result.authorized_categories:
            _section("Lab / report information", "lab_profile", _items(sm.important_reports, labels))
        snap = sm.patient_snapshot
        body = f'<div class="hb-ai-item">{snap.age if snap.age is not None else "—"} years · {esc((snap.sex or "—").title())}</div>'
        body += "".join(f'<div class="hb-ai-item">Allergy: {esc(a.text)}<div>{_cites(a.sources, labels)}</div></div>' for a in snap.allergies)
        body += "".join(f'<div class="hb-ai-item">{badge_html("Patient-provided", "violet", "person_edit")} {esc(p.text)}'
                        f'<div>{_cites(p.sources, labels)}</div></div>' for p in snap.patient_provided)
        _section("Patient snapshot", "person", body)

    with right:
        html('<div class="hb-section"><h3>⚠ Items Requiring Review</h3></div>')
        html(f"""<div class="hb-alert {'warning' if open_n else 'success'}">{icon('flag', 20, fill=True)}<div>
             <div class="t">{open_n} item{'s' if open_n != 1 else ''} require{'s' if open_n == 1 else ''} clinician review</div>
             <div class="b">Safety / Consistency Agent · documentation checks only — never a diagnosis.</div></div></div>""")
        for item in sm.items_for_review:
            flag = flags.get(item.flag_id)
            status = flag.status if flag else "open"
            label, tone = SEVERITY[item.severity]
            st_label, st_tone, st_ic = FLAG_STATUS.get(status, FLAG_STATUS["open"])
            with card(f"{key}_flag_{item.flag_id or abs(hash(item.issue))}"):
                html(f"""<div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center;margin-bottom:.4rem">
                     {badge_html(label, tone, "flag")}{badge_html(item.category.replace('_', ' ').title(), 'neutral')}
                     {badge_html(st_label, st_tone, st_ic)}</div>
                     <div style="font-weight:600;font-size:.9rem">{esc(item.issue)}</div>
                     <div class="hb-kv" style="margin-top:.5rem;font-size:.82rem"><span class="k">Reason</span><span class="v">{esc(item.evidence) or "—"}</span>
                     <span class="k">Source</span><span class="v">{_cites(item.sources, labels) or "—"}</span>
                     <span class="k">Action</span><span class="v">{esc(item.recommendation)}</span></div>""")
                if flag and flag.reviewed_by_name:
                    st.caption(f"{st_label} by {flag.reviewed_by_name} · {fmt_datetime(flag.reviewed_at)}")
                with st.container(horizontal=True, gap="small"):
                    if st.button("View source", key=f"{key}_src_{item.flag_id}", icon=":material/link:"):
                        _source_dialog(actor, patient_id, item.sources)
                    if item.flag_id and status == "open":
                        st.button("Accept", key=f"{key}_acc_{item.flag_id}", icon=":material/check:", type="primary",
                                  on_click=_review, args=(actor, item.flag_id, "accepted"))
                        st.button("Dismiss", key=f"{key}_dis_{item.flag_id}", icon=":material/close:",
                                  on_click=_review, args=(actor, item.flag_id, "dismissed"))
        if not sm.items_for_review:
            html('<div class="hb-card" style="font-size:.85rem;color:var(--hb-muted)">No documentation issues found.</div>')

        scope = " ".join(badge_html(RETRIEVAL_LABELS[k], "teal" if v else "neutral", "check" if v else "lock")
                         for k, v in result.retrieval.items())
        _section("Record Retrieval Agent", "verified_user",
                 f'<div class="hb-ai-item">{scope}</div><div class="hb-ai-item" style="font-size:.78rem;color:var(--hb-muted)">'
                 'Only consented records were retrieved; locked categories were never passed to the AI.</div>')
        if result.sources:
            ids = [s.id for s in result.sources]
            pick = st.selectbox("View any source", ids, key=f"{key}_srcpick",
                                format_func=lambda i: f"{i} · {labels.get(i, '')}")
            if st.button("Open source record", key=f"{key}_srcopen", icon=":material/open_in_new:"):
                _source_dialog(actor, patient_id, [pick])
    html(f'<div style="font-size:.78rem;color:var(--hb-muted);margin-top:.4rem">{icon("health_and_safety", 14)} {esc(DISCLAIMER)}</div>')


def _not_connected(key: str) -> bool:
    """No live AI: a calm configuration state (never an error). Returns True if a labelled demo run was requested."""
    html(f"""<div class="hb-card" style="text-align:center;padding:1.6rem 1rem">{tile_html("link_off", "neutral", 46, 24)}
      <div style="font-weight:800;font-size:1.05rem;margin-top:.6rem">AI is not connected.</div>
      <div style="font-size:.88rem;color:var(--hb-navy-600);margin-top:.2rem">Enter your own Gemini API key to enable the
        AI Clinical Copilot.</div></div>""")
    with st.container(horizontal=True, gap="small", horizontal_alignment="center"):
        if st.button("Configure AI", key=f"{key}_cfg_btn", icon=":material/key:", type="primary"):
            ss[f"{key}_cfg_open"] = True
        demo = st.button("Run demo analysis (no live AI)", key=f"{key}_demo", icon=":material/science:",
                         help="Deterministic rules only — clearly labelled as a demo response, not a live model.")
    return demo


def panel(actor: Actor, patient_id: int, patient_name: str, key: str, autorun: bool = False) -> None:
    """The full AI Clinical Copilot panel for one authorized patient."""
    try:
        with get_session() as s:
            counts = copilot_service.preview(s, actor, patient_id)
    except AccessDenied:
        alert_card("AI Clinical Copilot unavailable", "Patient access has not been granted for this doctor at this "
                   "organization — no records can be passed to the AI.", "lock")
        return
    total = sum(counts.values())
    provider = ai_settings.active_provider()
    html(f"""<div class="hb-card" style="display:flex;gap:1rem;align-items:center;flex-wrap:wrap">{tile_html("auto_awesome", "violet", 46, 24)}
      <div style="flex:1;min-width:240px"><div style="font-weight:800;font-size:1.02rem">AI Clinical Copilot</div>
        <div style="font-size:.86rem">{esc(patient_name)} · <b>{total} authorized record{'s' if total != 1 else ''}</b> available to analyse at
          {esc(actor.organization.name)}</div>
        <div style="font-size:.78rem;color:var(--hb-muted);margin-top:.15rem">Consent check → Record Retrieval Agent →
          Clinical Summary Agent → Safety / Consistency Agent → your review</div></div>{ai_settings.status_badge()}</div>""")
    alert_card("AI organises, summarises and flags possible discrepancies.",
               "It does not diagnose or change treatment. A clinician must verify every finding.", "ai")

    run = False
    if provider is None:
        run = _not_connected(key)
        autorun = False   # a shortcut never silently produces a demo response
    else:
        with st.container(horizontal=True, gap="small"):
            run = st.button("Generate Clinical Summary", key=f"{key}_gen", icon=":material/auto_awesome:", type="primary")
            if st.button("AI settings", key=f"{key}_cfg_btn", icon=":material/tune:"):
                ss[f"{key}_cfg_open"] = not ss.get(f"{key}_cfg_open", False)
    if ss.get(f"{key}_cfg_open"):
        ai_settings.config_section(key)

    result = None
    if run or autorun:
        with st.status("Checking consent…", expanded=True) as status:
            def progress(message: str) -> None:
                status.update(label=message)
                st.write(message)
                time.sleep(0.2)  # keep each agent step visible during the demo
            try:
                with get_session() as s:
                    result = copilot_service.generate(s, actor, patient_id, provider=provider, on_progress=progress)
                status.update(label="Summary ready for clinician review", state="complete", expanded=False)
            except AccessDenied as exc:
                status.update(label="Access denied", state="error")
                alert_card("Access denied", str(exc), "danger")
            except Exception:  # never let AI problems break the clinical workflow
                status.update(label="AI summary is temporarily unavailable.", state="error")
                alert_card("Live AI is currently unavailable.", "You can continue using HealthBridge normally.", "warning")
    else:
        try:
            with get_session() as s:
                result = copilot_service.latest(s, actor, patient_id)
        except AccessDenied:
            result = None
        if result:
            html(f'<div style="font-size:.8rem;color:var(--hb-muted);margin:.3rem 0">{icon("history", 14)} '
                 'Showing your most recent summary for this patient here. Generate again to refresh.</div>')
    if result:
        render(actor, patient_id, result, key)
    else:
        html('<div class="hb-card" style="font-size:.86rem;color:var(--hb-muted)">' + " ".join(
            badge_html(f"{RETRIEVAL_LABELS[k]} · {v}", "teal" if v else "neutral", "check" if v else "lock")
            for k, v in counts.items()) + "</div>")
