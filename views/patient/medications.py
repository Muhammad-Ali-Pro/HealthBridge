import streamlit as st

from core.db import get_session
from services import record_service
from ui.components import data_table, empty_state, esc, fmt_date, html, page_header, section_header, tile_html
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    record = record_service.own_record(s, actor)
current = [m for m in record.medications if m.current]
past = [m for m in record.medications if not m.current]

page_header("Medications", "The medicines your doctors have prescribed, and how to take them.", eyebrow="My HealthBridge")

section_header("Taking now", f"{len(current)} current")
if not current:
    empty_state("No current medications", icon_name="medication")
cols = st.columns(3)
for i, m in enumerate(current):
    with cols[i % 3]:
        html(f"""<div class="hb-card"><div style="display:flex;gap:.75rem;align-items:center">{tile_html("pill", "teal", 44, 24)}
          <div><div style="font-weight:800;font-size:1.05rem">{esc(m.drug_name)}</div>
          <div style="font-size:.85rem;color:var(--hb-navy-600)">{esc(m.strength)} · {esc(m.frequency)}</div></div></div>
          <div class="hb-kv" style="margin-top:.9rem"><span class="k">Prescribed by</span><span class="v">{esc(m.prescribed_by)}</span>
            <span class="k">Where</span><span class="v">{esc(m.organization_name)}</span>
            <span class="k">Started</span><span class="v">{esc(fmt_date(m.started))}</span>
            <span class="k">Course ends</span><span class="v">{esc(fmt_date(m.ends))}</span></div></div>""")

section_header("Previous medications")
data_table(["Medicine", "How to take", "Prescribed by", "When"], [[
    f'<span class="strong">{esc(m.drug_name)} {esc(m.strength)}</span>', esc(m.frequency),
    f'{esc(m.prescribed_by)}<div class="muted">{esc(m.organization_name)}</div>',
    f'{esc(fmt_date(m.started))} – {esc(fmt_date(m.ends))}',
] for m in past], empty="No previous medications")
