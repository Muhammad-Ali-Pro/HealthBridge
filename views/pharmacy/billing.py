import streamlit as st

from core.db import get_session
from services import pharmacy_service
from ui.components import alert_card, data_table, esc, fmt_when, kpi_row, page_header, payment_badge_html, phase_action
from ui.shell import current_actor

actor = current_actor()
with get_session() as s:
    invoices = pharmacy_service.list_invoices(s, actor)
    ov = pharmacy_service.billing_overview(s, actor)

head, actions = st.columns([3, 1], vertical_alignment="bottom")
with head:
    page_header("Billing", f"Invoices issued by {actor.organization.name} (simulated — no payment gateway)", eyebrow="Pharmacy")
with actions, st.container(horizontal=True, horizontal_alignment="right"):
    phase_action("Record payment", "payments", 3, key="record_payment", primary=True)

kpi_row([
    dict(label="Invoices", value=ov["invoices"], icon_name="receipt_long", tone="navy"),
    dict(label="Billed", value=f"PKR {ov['billed']:,.0f}", icon_name="request_quote", tone="blue"),
    dict(label="Collected", value=f"PKR {ov['collected']:,.0f}", icon_name="payments", tone="teal"),
    dict(label="Outstanding", value=f"PKR {ov['outstanding']:,.0f}", icon_name="pending", tone="amber"),
])
st.write("")
data_table(["Invoice", "Patient", "Items", "Total", "Paid", "Status", "Date"], [[
    f'<span class="strong">{esc(i.invoice_number)}</span><div class="muted">RX-{i.prescription_id:05d}</div>',
    esc(i.patient_name),
    "<br>".join(f"{esc(it['description'])} <span class='muted'>× {it['quantity']} @ {it['unit_price']:,.2f}</span>" for it in i.items),
    f'<span class="strong">{esc(i.currency)} {i.total:,.2f}</span>',
    f"{i.amount_paid:,.2f}",
    payment_badge_html(i.payment_status),
    f'<span class="muted">{esc(fmt_when(i.created_at))}</span>',
] for i in invoices], empty="No invoices yet")
alert_card("Billing is simulated", "Invoices are generated after dispensing for the demo. Payment status can be "
           "Pending, Paid, Partially paid or Cancelled.", "info")
