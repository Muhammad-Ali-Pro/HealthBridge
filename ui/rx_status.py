"""Read-only pharmacy progress for a prescription, shared by the patient and the doctor views.

Shows verification (or rejection reason), per-medicine dispensing progress and substitution requests.
Never shows pharmacist-internal notes (they are stripped before reaching these views). Billing is shown only
when the caller allows it — the patient yes, the doctor never (D8).
"""

from core.schemas import PrescriptionOut
from ui.components import badge_html, esc, fmt_date, fmt_datetime, icon, invoice_items_html, payment_badge_html

LINE_STYLE = {
    "dispensed": ("Dispensed", "teal", "check_circle"),
    "partial": ("Partly dispensed", "amber", "hourglass_bottom"),
    "unavailable": ("Unavailable", "coral", "remove_shopping_cart"),
    "substitution_requested": ("Substitution requested", "blue", "swap_horiz"),
    "pending": ("Not yet dispensed", "neutral", "schedule"),
}


def item_progress(rx: PrescriptionOut) -> list[dict]:
    """Per prescribed medicine: prescribed, dispensed so far, outstanding, latest line status."""
    out = []
    for item in rx.items:
        lines = [line for d in rx.dispensings for line in d.items
                 if line.get("item_id") == item.id or (line.get("item_id") is None and line.get("drug_name") == item.drug_name)]
        dispensed = sum(int(line.get("quantity_dispensed") or 0) for line in lines)
        status = "dispensed" if dispensed >= item.quantity else (lines[-1].get("status", "pending") if lines else "pending")
        if status == "dispensed" and dispensed < item.quantity:
            status = "partial"
        out.append({"item": item, "prescribed": item.quantity, "dispensed": dispensed,
                    "outstanding": max(item.quantity - dispensed, 0), "status": status})
    return out


def substitution_requests(rx: PrescriptionOut) -> list[tuple]:
    return [(d.dispensed_at, d.pharmacy_name, d.substitutions) for d in rx.dispensings if d.substitutions]


def pharmacy_updates_html(rx: PrescriptionOut, show_billing: bool = False) -> str:
    if rx.status in ("draft", "issued"):
        return ""
    parts = []
    if rx.status == "rejected":
        parts.append(f'<div class="hb-plain" style="background:var(--hb-coral-50);color:#8A2E20">{icon("block", 16)}'
                     f'Rejected by {esc(rx.pharmacy_name or "the pharmacy")}: {esc(rx.status_reason or "no reason given")}</div>')
    elif rx.verified_at:
        parts.append(f'<div style="font-size:.82rem;margin-bottom:.4rem">{icon("fact_check", 16)} Verified by '
                     f'{esc(rx.verified_by_name or "the pharmacist")} at {esc(rx.pharmacy_name or "")} · '
                     f'{esc(fmt_datetime(rx.verified_at))}</div>')
    else:
        parts.append(f'<div style="font-size:.82rem;margin-bottom:.4rem">{icon("schedule", 16)} Waiting for '
                     f'{esc(rx.pharmacy_name or "the pharmacy")} to verify</div>')
    if rx.dispensings or rx.status in ("verified", "partially_dispensed", "dispensed"):
        rows = "".join(
            f"<tr><td class='strong'>{esc(p['item'].drug_name)} {esc(p['item'].strength)}</td><td>{p['prescribed']}</td>"
            f"<td>{p['dispensed']}</td><td>{p['outstanding']}</td><td>{badge_html(*LINE_STYLE[p['status']])}</td></tr>"
            for p in item_progress(rx))
        parts.append('<div class="hb-table-wrap"><table class="hb-table"><thead><tr><th>Medicine</th><th>Prescribed</th>'
                     f'<th>Dispensed</th><th>Outstanding</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>')
    for when, pharmacy, text in substitution_requests(rx):
        parts.append(f'<div class="hb-plain" style="margin-top:.5rem">{icon("swap_horiz", 16)}<span><b>Substitution request</b> '
                     f'from {esc(pharmacy)} · {esc(fmt_datetime(when))}: {esc(text)} — nothing was substituted; '
                     'the prescriber decides.</span></div>')
    if show_billing:
        for inv in rx.invoices:
            parts.append(f'<div style="margin-top:.6rem;font-size:.82rem">{icon("receipt_long", 14)} <b>{esc(inv.invoice_number)}</b> · '
                         f'{esc(inv.currency)} {inv.total:,.2f} · paid {inv.amount_paid:,.2f} {payment_badge_html(inv.payment_status)}</div>'
                         f'<div class="hb-table-wrap">{invoice_items_html(inv)}</div>')
    return "".join(parts)


def patient_plain_status(rx: PrescriptionOut) -> str:
    """One plain-language sentence for the patient."""
    pharmacy = rx.pharmacy_name or "your pharmacy"
    progress = item_progress(rx)
    waiting = [p for p in progress if p["outstanding"]]
    unavailable = [p["item"].drug_name for p in progress if p["status"] == "unavailable"]
    asked = [p["item"].drug_name for p in progress if p["status"] == "substitution_requested"]
    extra = ""
    if unavailable:
        extra += f" {', '.join(unavailable)} {'is' if len(unavailable) == 1 else 'are'} currently unavailable at {pharmacy}."
    if asked:
        extra += f" {pharmacy} asked your doctor about an alternative for {', '.join(asked)}."
    billing = ""
    if rx.invoices:
        inv = rx.invoices[-1]
        billing = f" Invoice {inv.invoice_number}: {inv.payment_status.replace('_', ' ')}."
    return {
        "issued": "Ready to send. Choose the pharmacy where you want to collect your medicine.",
        "sent": f"Sent to {pharmacy}. The pharmacist will check it before it's ready.",
        "verified": f"Checked by {pharmacy} and ready for you to collect." + extra,
        "partially_dispensed": f"Part of your medicine was collected from {pharmacy}; "
                               f"{sum(p['outstanding'] for p in waiting)} still to collect." + extra + billing,
        "dispensed": f"Collected from {pharmacy}" + (f" on {fmt_date(rx.dispensed_at)}." if rx.dispensed_at else ".") + billing,
        "rejected": f"{pharmacy} could not fill this prescription ({rx.status_reason or 'no reason given'}). "
                    "Please contact your doctor.",
        "cancelled": "Your doctor cancelled this prescription.",
    }.get(rx.status, "")
