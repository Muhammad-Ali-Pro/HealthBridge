import streamlit as st

from core.db import get_session
from services import record_service
from ui.components import (
    ORG_STYLE,
    TIMELINE_FILTERS,
    esc,
    filter_timeline,
    fmt_date,
    html,
    page_header,
    plural,
    section_header,
    timeline,
    timeline_group,
)
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)
events = record.timeline

page_header("My Medical Timeline", "Everything in one place, in the order it happened — every entry keeps its source.",
            eyebrow="My HealthBridge")

counts = {f: len(events) if f == "All" else sum(timeline_group(e) == f for e in events) for f in TIMELINE_FILTERS}
choice = st.segmented_control("Filter", TIMELINE_FILTERS, default="All", required=True, key="pt_tl_filter",
                              label_visibility="collapsed", format_func=lambda f: f"{f} ({counts[f]})")
st.write("")
orgs = sorted({(e.organization_name, e.organization_type) for e in events if e.organization_name})
left, right = st.columns([1, 2.6], gap="large")
with left:
    rows = "".join(f'<div style="display:flex;justify-content:space-between;font-size:.82rem;padding:.3rem 0">'
                   f'<span>{esc(n)}</span><span style="color:var(--hb-muted)">{esc(ORG_STYLE[t][0])}</span></div>' for n, t in orgs)
    first = fmt_date(events[-1].occurred_at) if events else "—"
    html(f"""<div class="hb-card"><div class="hb-kv"><span class="k">Records</span><span class="v">{len(events)}</span>
             <span class="k">Since</span><span class="v">{esc(first)}</span>
             <span class="k">Sources</span><span class="v">{len(orgs)} organizations + you</span></div>
             <div style="margin-top:.7rem;border-top:1px solid var(--hb-border);padding-top:.5rem">{rows}</div></div>""")
with right:
    shown = filter_timeline(events, choice)
    section_header("Timeline", f"{plural(len(shown), 'record')} · newest first")
    with st.container(key="hbcard_pt_timeline"):
        timeline(shown)
