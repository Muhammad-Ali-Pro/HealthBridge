"""Rendering of a Clinical Copilot result: sections, citations, review items, provenance and disclaimer."""

import streamlit as st

from agents.schemas import NOT_DOCUMENTED, CopilotResult
from ui.components import CATEGORY_STYLE, badge_html, esc, fmt_datetime, html, icon

SEVERITY = {"high": ("High", "coral"), "medium": ("Medium", "amber"), "low": ("Low", "blue")}


def _cites(ids: list[str], labels: dict[str, str]) -> str:
    return "".join(f'<span class="hb-cite" title="{esc(labels.get(i, i))}">{esc(i)}</span>' for i in ids)


def _section(title: str, ic: str, body: str) -> None:
    html(f"""<div class="hb-ai-out" style="margin-bottom:.8rem"><div class="hb-ai-h"><h4>{icon(ic, 18)} {esc(title)}</h4>
             </div>{body}</div>""")


def _items(items, labels, empty=NOT_DOCUMENTED) -> str:
    if not items:
        return f'<div class="hb-ai-item" style="color:var(--hb-muted)">{esc(empty)}</div>'
    return "".join(f'<div class="hb-ai-item">{esc(i.text)}<div>{_cites(i.sources, labels)}</div></div>' for i in items)


def render(result: CopilotResult) -> None:
    labels = {s.id: f"{s.label} {s.date}".strip() for s in result.sources}
    s = result.summary
    generator = (badge_html("AI-generated · needs review", "violet", "auto_awesome") if result.generator == "llm"
                 else badge_html("Rule-based summary (AI unavailable)", "neutral", "rule"))
    html(f"""<div class="hb-alert ai">{icon("auto_awesome", 20, fill=True)}<div><div class="t">AI-generated summary for clinician review</div>
         <div class="b">It does not diagnose, prescribe, or modify treatment. Verify against the underlying patient record.</div></div></div>""")
    html(f"""<div class="hb-card" style="display:flex;gap:1.2rem;flex-wrap:wrap;align-items:center;justify-content:space-between">
      <div><div class="hb-form-section">Patient</div><b>{esc(result.patient_name)}</b> · {esc(result.patient_display_id)}</div>
      <div><div class="hb-form-section">Requested by</div>{esc(result.provider_name)} · {esc(result.organization_name)}</div>
      <div><div class="hb-form-section">Generated</div>{esc(fmt_datetime(result.generated_at))}</div>
      <div>{generator}</div></div>""")
    for n in result.notices:
        html(f'<div class="hb-alert warning">{icon("info", 20, fill=True)}<div><div class="b">{esc(n)}</div></div></div>')
    if result.removed_unsupported:
        html(f'<div class="hb-alert info">{icon("fact_check", 20, fill=True)}<div><div class="b">{result.removed_unsupported} '
             f'AI statement(s) without a verifiable source in the authorized records were removed.</div></div></div>')

    left, right = st.columns([3, 2], gap="large")
    with left:
        snap = s.patient_snapshot
        body = (f'<div class="hb-ai-item">{snap.age if snap.age is not None else "—"} years · {esc((snap.sex or "—").title())}'
                f'<div>{_cites(["PROFILE"], labels)}</div></div>')
        body += "".join(f'<div class="hb-ai-item">Allergy: {esc(a.text)}<div>{_cites(a.sources, labels)}</div></div>' for a in snap.allergies)
        body += "".join(f'<div class="hb-ai-item">{badge_html("Patient-provided", "violet", "person_edit")} {esc(p.text)}'
                        f'<div>{_cites(p.sources, labels)}</div></div>' for p in snap.patient_provided)
        _section("Patient snapshot", "person", body)
        _section("Active conditions (as documented)", "monitor_heart", _items(s.active_conditions, labels))
        meds = ("".join(f"""<div class="hb-ai-item"><b>{esc(m.medicine)}</b> · {esc(m.strength)} · {esc(m.dosage)} · {esc(m.frequency)}
                   <div style="font-size:.76rem;color:var(--hb-muted)">Since {esc(m.date)} · Source: {esc(labels.get(m.sources[0], '') if m.sources else 'not cited')}</div>
                   <div>{_cites(m.sources, labels)}</div></div>""" for m in s.current_medications)
                or f'<div class="hb-ai-item" style="color:var(--hb-muted)">{NOT_DOCUMENTED}</div>')
        _section("Current medications", "medication", meds)
        _section("Recent clinical history", "history", _items(s.recent_history, labels))
        _section("Recent prescriptions", "prescriptions", _items(s.recent_prescriptions, labels))
        if any(c in result.authorized_categories for c in ("lab_reports", "imaging_reports")):
            _section("Important lab / report information", "lab_profile", _items(s.important_reports, labels))
        else:
            _section("Important lab / report information", "lock",
                     '<div class="hb-ai-item" style="color:var(--hb-muted)">Laboratory reports are not shared with you — '
                     'not included in this summary.</div>')
    with right:
        rows = []
        for it in s.items_for_review:
            label, tone = SEVERITY[it.severity]
            rows.append(f"""<div class="hb-ai-item"><div style="display:flex;gap:.4rem;align-items:center;margin-bottom:.3rem">
              {badge_html(label, tone, "flag")}</div><div style="font-weight:600">{esc(it.issue)}</div>
              <div style="font-size:.8rem;color:var(--hb-navy-600);margin-top:.25rem">{esc(it.evidence)}</div>
              <div style="font-size:.78rem;margin-top:.3rem">{icon("arrow_right_alt", 14)} {esc(it.recommendation)}</div>
              <div>{_cites(it.sources, labels)}</div></div>""")
        _section(f"Potential items to review ({len(s.items_for_review)})", "flag",
                 "".join(rows) or '<div class="hb-ai-item" style="color:var(--hb-muted)">No documentation issues found.</div>')
        scope = " ".join(badge_html(CATEGORY_STYLE.get(c, (c,))[0], "teal", "check") for c in result.authorized_categories)
        counts = " · ".join(f"{v} {k.replace('_', ' ')}" for k, v in result.record_counts.items() if v)
        _section("Authorized input", "verified_user",
                 f'<div class="hb-ai-item">{scope}</div><div class="hb-ai-item" style="font-size:.8rem">{esc(counts) or "No records"}</div>'
                 '<div class="hb-ai-item" style="font-size:.78rem;color:var(--hb-muted)">Only these consented records were '
                 'given to the AI. It never queries the database.</div>')
        src_rows = "".join(f'<div class="hb-ai-item" style="font-size:.8rem"><span class="hb-cite">{esc(x.id)}</span> '
                           f'{esc(x.label)} {esc(x.date)}</div>' for x in result.sources)
        _section(f"Sources ({len(result.sources)})", "link", src_rows)
    html(f'<div style="font-size:.78rem;color:var(--hb-muted);margin-top:.4rem">{icon("health_and_safety", 14)} {esc(result.disclaimer)}</div>')
