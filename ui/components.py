"""Reusable HealthBridge UI components (design system).

`*_html` functions return markup for composition; the plain-named functions render.
All user/record text is escaped with `esc()` before being placed in markup.
"""

import html as _html
from collections.abc import Sequence
from datetime import datetime, timezone

import streamlit as st

from core.schemas import (
    AccessDecision,
    DocumentOut,
    InvoiceOut,
    LabOrderOut,
    PatientEntryOut,
    PatientIdentity,
    PatientOut,
    PrescriptionOut,
    TimelineEventOut,
)

# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def esc(value) -> str:
    return _html.escape("" if value is None else str(value))


def html(markup: str, width: str = "stretch") -> None:
    """Render raw markup. Collapsed to one line so Markdown never treats indentation as code."""
    body = " ".join(line.strip() for line in markup.splitlines())
    st.markdown(f'<div class="hb-html">{body}</div>', unsafe_allow_html=True, width=width)


def icon(name: str, size: int = 20, fill: bool = False) -> str:
    return f'<span class="hb-icon{" fill" if fill else ""}" style="font-size:{size}px">{name}</span>'


def tile_html(icon_name: str, tone: str, size: int = 34, icon_size: int = 18) -> str:
    return (f'<span class="hb-tile tone-{tone}" style="width:{size}px;height:{size}px">'
            f'{icon(icon_name, icon_size)}</span>')


def initials(name: str) -> str:
    parts = [p for p in name.replace("Dr.", "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def avatar_html(name: str, size: int = 40) -> str:
    return (f'<span class="hb-avatar" style="width:{size}px;height:{size}px;font-size:{size * 0.38:.0f}px">'
            f'{esc(initials(name))}</span>')


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ---------------------------------------------------------------------------
# Time formatting (stored as naive UTC, shown in the machine's local time)
# ---------------------------------------------------------------------------


def _local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone()


def local_now() -> datetime:
    """The current local time (aware). Forms read 'now' through this one function."""
    return datetime.now().astimezone()


def to_local(dt: datetime) -> datetime:
    """Naive-UTC timestamp → aware local datetime (for editing in forms)."""
    return _local(dt)


def local_to_utc(local_date, local_time) -> datetime:
    """Local date + time from a form → naive UTC for storage."""
    aware = datetime.combine(local_date, local_time).astimezone()
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def fmt_date(dt: datetime) -> str:
    return _local(dt).strftime("%d %b %Y")


def fmt_time(dt: datetime) -> str:
    return _local(dt).strftime("%H:%M")


def fmt_datetime(dt: datetime) -> str:
    return _local(dt).strftime("%d %b %Y, %H:%M")


def fmt_when(dt: datetime) -> str:
    """'Today, 14:20' / 'Yesterday, 09:05' / '12 Aug 2026'."""
    local, now = _local(dt), datetime.now().astimezone()
    days = (now.date() - local.date()).days
    if days == 0:
        return f"Today, {local:%H:%M}"
    if days == 1:
        return f"Yesterday, {local:%H:%M}"
    return local.strftime("%d %b %Y")


def fmt_ago(dt: datetime) -> str:
    seconds = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).total_seconds()
    if seconds < 3600:
        return f"{max(int(seconds // 60), 1)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{plural(int(seconds // 86400), 'day')} ago"


# ---------------------------------------------------------------------------
# Vocabularies: organizations, record categories, statuses
# ---------------------------------------------------------------------------

ORG_STYLE = {
    "clinic": ("Clinic", "stethoscope", "teal"),
    "hospital": ("Hospital", "local_hospital", "blue"),
    "laboratory": ("Laboratory", "biotech", "navy"),
    "pharmacy": ("Pharmacy", "local_pharmacy", "amber"),
}
CATEGORY_STYLE = {
    "consultations": ("Previous consultations", "stethoscope"),
    "prescriptions": ("Prescriptions", "prescriptions"),
    "medications": ("Current medications", "medication"),
    "lab_reports": ("Laboratory reports", "biotech"),
    "hospital_records": ("Hospital records", "local_hospital"),
    "imaging_reports": ("Imaging", "radiology"),
    "documents": ("Documents", "description"),
}
STATUS_STYLE = {
    "draft": ("Draft", "neutral", "edit_note"),
    "issued": ("Choose a pharmacy", "navy", "storefront"),
    "sent": ("Awaiting verification", "blue", "schedule"),
    "verified": ("Ready to dispense", "amber", "fact_check"),
    "partially_dispensed": ("Partially dispensed", "amber", "hourglass_bottom"),
    "dispensed": ("Dispensed", "teal", "check_circle"),
    "rejected": ("Rejected", "coral", "block"),
    "cancelled": ("Cancelled", "neutral", "cancel"),
}
PAYMENT_STYLE = {
    "pending": ("Payment pending", "amber", "schedule"),
    "paid": ("Paid", "teal", "check_circle"),
    "partially_paid": ("Partially paid", "blue", "hourglass_bottom"),
    "cancelled": ("Cancelled", "neutral", "cancel"),
}
DOC_TYPE_LABELS = {
    "medical_report": "Medical report", "lab_report": "Lab report", "imaging_report": "Imaging report",
    "referral_letter": "Referral letter", "discharge_summary": "Discharge summary",
    "prescription": "Prescription document", "other": "Document",
}
ENTRY_TYPE_STYLE = {
    "note": ("Health note", "edit_note"), "allergy": ("Allergy", "warning"), "condition": ("Condition", "monitor_heart"),
    "medication": ("Medication", "medication"), "other": ("Information", "info"),
}
LAB_STATUS_STYLE = {
    "ordered": ("New order", "blue", "inbox"),
    "received": ("In progress", "navy", "science"),
    "resulted": ("Awaiting verification", "amber", "pending_actions"),
    "verified": ("Ready to publish", "amber", "fact_check"),
    "published": ("Published", "teal", "check_circle"),
}
CONSENT_STATUS_STYLE = {
    "active": ("Active", "teal", "check_circle"),
    "revoked": ("Revoked", "neutral", "block"),
    "expired": ("Expired", "neutral", "timer_off"),
}
DURATION_LABELS = {
    "until_revoked": "Until I revoke it",
    "one_consultation": "One consultation",
    "hours_24": "24 hours",
    "days_7": "7 days",
}
SEVERITY_STYLE = {"high": ("High", "coral"), "warning": ("Warning", "amber"), "info": ("Info", "blue")}


def badge_html(label: str, tone: str = "neutral", icon_name: str | None = None) -> str:
    ic = icon(icon_name, 14, fill=True) if icon_name else ""
    return f'<span class="hb-badge tone-{tone}">{ic}{esc(label)}</span>'


def status_badge_html(status: str) -> str:
    label, tone, ic = STATUS_STYLE.get(status, (status.title(), "neutral", None))
    return badge_html(label, tone, ic)


def payment_badge_html(status: str) -> str:
    label, tone, ic = PAYMENT_STYLE.get(status, (status.title(), "neutral", None))
    return badge_html(label, tone, ic)


def patient_provided_badge_html(label: str = "Patient-provided") -> str:
    return badge_html(label, "violet", "person_edit")


def source_html(source_type: str, organization_name: str | None, organization_type: str | None,
                person: str | None = None) -> str:
    """Record provenance: 'Patient-provided', or organization badge + person."""
    if source_type == "patient":
        return patient_provided_badge_html()
    who = f'<span class="hb-src-person">{icon("person", 14)} {esc(person)}</span>' if person else ""
    return f"{org_badge_html(organization_name, organization_type)}{who}"


def lab_status_badge_html(status: str) -> str:
    label, tone, ic = LAB_STATUS_STYLE.get(status, (status.title(), "neutral", None))
    return badge_html(label, tone, ic)


def consent_status_badge_html(status: str) -> str:
    label, tone, ic = CONSENT_STATUS_STYLE.get(status, (status.title(), "neutral", None))
    return badge_html(label, tone, ic)


def severity_badge_html(severity: str) -> str:
    label, tone = SEVERITY_STYLE.get(severity, (severity.title(), "neutral"))
    return badge_html(label, tone, "error")


def ai_badge_html(label: str = "AI-generated · needs review") -> str:
    return badge_html(label, "violet", "auto_awesome")


def verified_badge_html(label: str = "Clinical record") -> str:
    return badge_html(label, "teal", "verified")


def org_badge_html(name: str | None, org_type: str | None) -> str:
    if not name:
        return ""
    _, ic, tone = ORG_STYLE.get(org_type or "", ("", "domain", "neutral"))
    return f'<span class="hb-org tone-{tone}">{icon(ic, 14)}{esc(name)}</span>'


def org_type_label(org_type: str) -> str:
    return ORG_STYLE.get(org_type, (org_type.title(),))[0]


def chips_html(items: Sequence[str], tone: str = "neutral", icon_name: str | None = None, empty: str = "None recorded") -> str:
    if not items:
        return f'<span class="hb-chip tone-neutral">{esc(empty)}</span>'
    ic = icon(icon_name, 14) if icon_name else ""
    return "".join(f'<span class="hb-chip tone-{tone}">{ic}{esc(i)}</span>' for i in items)


def allergy_chips_html(allergies: Sequence[str]) -> str:
    return chips_html(allergies, "coral", "warning", empty="No known allergies")


def condition_chips_html(conditions: Sequence[str] | None) -> str:
    if conditions is None:
        return f'<span class="hb-chip tone-neutral">{icon("lock", 14)}Not shared with you</span>'
    return chips_html(conditions, "navy", None, empty="No conditions recorded")


def category_chips_html(categories: Sequence[str], tone: str = "teal", locked: bool = False) -> str:
    parts = []
    for c in categories:
        label, ic = CATEGORY_STYLE.get(c, (c.replace("_", " ").title(), "description"))
        parts.append(f'<span class="hb-chip tone-{tone}">{icon("lock" if locked else ic, 14)}{esc(label)}</span>')
    return "".join(parts)


def scope_summary(scope_type: str | None, categories: Sequence[str]) -> str:
    return "All records" if scope_type == "all" else "Selected records"


# ---------------------------------------------------------------------------
# Layout blocks
# ---------------------------------------------------------------------------


def page_header(title: str, subtitle: str | None = None, eyebrow: str | None = None) -> None:
    eb = f'<div class="hb-eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    sub = f'<div class="hb-page-sub">{esc(subtitle)}</div>' if subtitle else ""
    html(f'<div class="hb-page-header"><div>{eb}<h1 class="hb-page-title">{esc(title)}</h1>{sub}</div></div>')


def section_header(title: str, hint: str | None = None) -> None:
    h = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    html(f'<div class="hb-section"><h3>{esc(title)}</h3>{h}</div>')


def card(key: str, selected: bool = False):
    """A white rounded card that can hold native Streamlit widgets. Use as a context manager."""
    return st.container(key=f"hbcard{'_sel' if selected else ''}_{key}")


def kpi_card(label: str, value, icon_name: str, tone: str = "teal", foot: str | None = None) -> None:
    f = f'<div class="foot">{esc(foot)}</div>' if foot else '<div class="foot">&nbsp;</div>'
    html(f"""
      <div class="hb-kpi">
        <div class="top"><span class="label">{esc(label)}</span>
          <span class="tile tone-{tone}">{icon(icon_name, 20)}</span></div>
        <div class="value">{esc(value)}</div>{f}
      </div>""")


def kpi_row(cards: Sequence[dict]) -> None:
    for col, spec in zip(st.columns(len(cards)), cards):
        with col:
            kpi_card(**spec)


def alert_card(title: str, body: str = "", tone: str = "info", icon_name: str | None = None, body_html: bool = False) -> None:
    default_icons = {"warning": "warning", "danger": "error", "info": "info", "success": "check_circle",
                     "ai": "auto_awesome", "lock": "lock"}
    ic = icon(icon_name or default_icons.get(tone, "info"), 20, fill=True)
    b = f'<div class="b">{body if body_html else esc(body)}</div>' if body else ""
    html(f'<div class="hb-alert {tone}">{ic}<div><div class="t">{esc(title)}</div>{b}</div></div>')


def empty_state(title: str, body: str = "", icon_name: str = "inbox", tone: str = "teal", boxed: bool = True) -> None:
    b = f'<div class="b">{esc(body)}</div>' if body else ""
    inner = (f'<div class="hb-empty"><div class="tile tone-{tone}">{icon(icon_name, 26)}</div>'
             f'<div class="t">{esc(title)}</div>{b}</div>')
    html(f'<div class="hb-card">{inner}</div>' if boxed else inner)


def data_table(headers: Sequence[str], rows: Sequence[Sequence[str]], empty: str = "Nothing to show yet") -> None:
    """Rows are pre-rendered cell markup — escape text with esc()."""
    if not rows:
        empty_state(empty, icon_name="table_rows", tone="neutral")
        return
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    html(f'<div class="hb-table-wrap"><table class="hb-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def quick_actions(actions: Sequence[tuple[str, str, str]], key: str = "main") -> None:
    """actions: (page path, label, material icon name)."""
    with st.container(key=f"hb_qa_{key}"):
        for col, (page, label, ic) in zip(st.columns(len(actions)), actions):
            with col:
                st.page_link(page, label=label, icon=f":material/{ic}:", width="stretch")


def phase_action(label: str, icon_name: str, phase: int, key: str, primary: bool = False, stretch: bool = False) -> None:
    """A real-looking action button whose workflow lands in a later build phase."""
    if st.button(label, key=key, icon=f":material/{icon_name}:", type="primary" if primary else "secondary",
                 width="stretch" if stretch else "content"):
        st.toast(f"**{label}** arrives in Phase {phase}.", icon=":material/construction:")


def disclaimer_footer() -> None:
    html(f"""<div class="hb-footer">{icon("health_and_safety", 16)}
      Synthetic demo data. Patients control who can see their records. AI organises and flags possible
      discrepancies for clinician review — it never diagnoses or changes treatment.</div>""")


# ---------------------------------------------------------------------------
# Domain components
# ---------------------------------------------------------------------------


def patient_meta(p: PatientIdentity) -> str:
    return f"{p.age} yrs · {p.sex.title()} · {p.display_id}"


def patient_identity_html(p: PatientIdentity, right: str = "", size: int = 44) -> str:
    return f"""
      <div class="hb-patient">{avatar_html(p.name, size)}
        <div class="body"><div class="name">{esc(p.name)}</div><div class="meta" style="margin-bottom:0">{esc(patient_meta(p))}</div></div>
        {right}
      </div>"""


def patient_card_html(p: PatientOut, extra: str = "") -> str:
    return f"""
      <div class="hb-patient">{avatar_html(p.name, 44)}
        <div class="body">
          <div class="name">{esc(p.name)}</div>
          <div class="meta">{esc(patient_meta(p))}</div>
          <div>{allergy_chips_html(p.allergies)}</div>
          <div>{condition_chips_html(p.conditions)}</div>{extra}
        </div>
      </div>"""


def access_status_html(decision: AccessDecision, organization_name: str | None = None, extra: str = "") -> str:
    """Doctor-facing access state for a patient: green with scope, or locked."""
    if decision.allowed:
        scope = (badge_html("All records", "teal", "select_all") if decision.scope_type == "all"
                 else category_chips_html(decision.categories))
        where = f" at {esc(organization_name)}" if organization_name else ""
        return f"""
          <div class="hb-access ok">{icon("verified_user", 18, fill=True)}
            <div><div class="t">Patient has granted you access{where}</div>
            <div class="s">{scope}</div>{extra}</div></div>"""
    return f"""
      <div class="hb-access locked">{icon("lock", 18, fill=True)}
        <div><div class="t">Records unavailable</div><div class="s">{esc(decision.reason)}</div></div></div>"""


RX_STEPS = [("issued", "Prescribed"), ("sent", "Sent to pharmacy"), ("verified", "Verified"),
            ("dispensed", "Dispensed"), ("billed", "Billed")]


def rx_progress_html(rx: PrescriptionOut) -> str:
    """Stepper: prescribed → sent → verified → dispensed → billed."""
    order = {"issued": 0, "sent": 1, "verified": 2, "partially_dispensed": 2, "dispensed": 3}
    reached = order.get(rx.status, -1) + (1 if rx.invoice else 0)
    if rx.status in ("rejected", "cancelled"):
        return f'<div class="hb-plain" style="background:var(--hb-coral-50);color:#8A2E20">{icon("block", 16)}{esc(STATUS_STYLE[rx.status][0])}{": " + esc(rx.status_reason) if rx.status_reason else ""}</div>'
    steps = "".join(
        f'<div class="hb-step{" done" if i <= reached else ""}"><span class="dot">{icon("check" if i <= reached else "circle", 14)}</span>'
        f'<span class="lbl">{esc(label)}</span></div>' for i, (_, label) in enumerate(RX_STEPS))
    return f'<div class="hb-steps">{steps}</div>'


def prescription_card_html(rx: PrescriptionOut, show_patient: bool = True, plain_status: str | None = None,
                           progress: bool = False) -> str:
    title = rx.patient_name if show_patient else f"Prescription {rx.display_id}"
    sub = f"{rx.display_id} · {rx.provider_name}" if show_patient else rx.provider_name
    drugs = "".join(f"""
      <div class="drug">{tile_html("pill", "teal", 32, 18)}
        <div><div class="n">{esc(i.drug_name)} {esc(i.strength)}</div>
        <div class="d">{esc(i.dosage + " · " if i.dosage else "")}{esc(i.frequency)} · {i.duration_days} days · qty {i.quantity}</div></div></div>""" for i in rx.items)
    progress_html = rx_progress_html(rx) if progress else ""
    billing = (f'<div style="margin-top:.5rem;font-size:.78rem;color:var(--hb-muted)">{icon("receipt_long", 14)} '
               f'{esc(rx.invoice.invoice_number)} · PKR {rx.invoice.total:,.0f} {payment_badge_html(rx.invoice.payment_status)}</div>'
               if rx.invoice else "")
    allergy = ""
    if show_patient and rx.patient_allergies:
        allergy = f'<div style="margin-top:.6rem">{allergy_chips_html(rx.patient_allergies)}</div>'
    plain = f'<div class="hb-plain">{icon("info", 16)}{esc(plain_status)}</div>' if plain_status else ""
    pharmacy = f"{icon('local_pharmacy', 14)} {esc(rx.pharmacy_name)}" if rx.pharmacy_name else ""
    return f"""
      <div class="hb-rx">
        <div class="head"><div class="title">{esc(title)}</div>{status_badge_html(rx.status)}</div>
        <div class="sub">{esc(sub)}</div>
        <div style="margin-top:.45rem">{org_badge_html(rx.organization_name, rx.organization_type)}</div>
        {drugs}{allergy}{plain}{progress_html}{billing}
        <div class="foot"><span>{pharmacy}</span><span>{icon("schedule", 14)} {esc(fmt_when(rx.created_at))}</span></div>
      </div>"""


def prescription_card(rx: PrescriptionOut, show_patient: bool = True, plain_status: str | None = None,
                      progress: bool = False) -> None:
    html(f'<div class="hb-card">{prescription_card_html(rx, show_patient, plain_status, progress)}</div>')


def organization_card_html(name: str, org_type: str, subtitle: str = "", extra: str = "") -> str:
    label, ic, tone = ORG_STYLE.get(org_type, (org_type.title(), "domain", "neutral"))
    return f"""<div class="hb-entity">{tile_html(ic, tone, 44, 24)}
      <div style="min-width:0"><div class="nm">{esc(name)}</div><div class="sb">{esc(label)}{" · " + esc(subtitle) if subtitle else ""}</div></div>
      </div>{extra}"""


def provider_card_html(name: str, specialty: str | None, organizations: Sequence[str] = (), extra: str = "") -> str:
    orgs = "".join(f'<div style="font-size:.8rem;color:var(--hb-navy-600);margin-top:.2rem">{icon("domain", 14)} {esc(o)}</div>'
                   for o in organizations)
    return f"""<div class="hb-entity" style="align-items:flex-start">{avatar_html(name, 44)}
      <div style="min-width:0"><div class="nm">{esc(name)}</div><div class="sb">{esc(specialty or "Doctor")}</div>{orgs}{extra}</div></div>"""


def consent_scope_html(scope_type: str, categories: Sequence[str]) -> str:
    return (badge_html("All records", "coral", "select_all") if scope_type == "all"
            else category_chips_html(categories))


def consent_card_html(c, meta: str = "") -> str:
    """c: ConsentOut. Provider + organization + status + scope — the unit of patient-controlled access."""
    return f"""
      <div style="display:flex;gap:.8rem;align-items:flex-start">{avatar_html(c.provider_name, 44)}
        <div style="flex:1;min-width:0">
          <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center">
            <span style="font-weight:700">{esc(c.provider_name)}</span>{consent_status_badge_html(c.status)}</div>
          <div style="margin:.3rem 0 .55rem">{org_badge_html(c.organization_name, c.organization_type)}</div>
          <div style="font-size:.78rem;color:var(--hb-muted);margin-bottom:.35rem">Access:
            <b style="color:var(--hb-navy)">{"All records" if c.scope_type == "all" else "Selected records"}</b></div>
          <div>{consent_scope_html(c.scope_type, c.categories)}</div>
          {f'<div style="font-size:.76rem;color:var(--hb-muted);margin-top:.45rem">{meta}</div>' if meta else ""}
        </div></div>"""


def document_card_html(d: DocumentOut) -> str:
    src = (patient_provided_badge_html("Patient uploaded") if d.source_type == "patient"
           else f'{badge_html(d.source, "neutral", "upload_file")}')
    return f"""
      <div style="display:flex;gap:.75rem;align-items:flex-start">{tile_html("description", "navy", 40, 22)}
        <div style="flex:1;min-width:0">
          <div style="font-weight:700;font-size:.9rem">{esc(d.title)}</div>
          <div style="font-size:.76rem;color:var(--hb-muted);margin:.1rem 0 .4rem">{esc(DOC_TYPE_LABELS.get(d.doc_type, "Document"))}
            · {esc(d.file_name or "metadata only")} · {esc(fmt_date(d.created_at))}</div>
          <div>{src}</div>
          {f'<div style="font-size:.8rem;margin-top:.35rem;color:var(--hb-navy-600)">{esc(d.description)}</div>' if d.description else ""}
        </div></div>"""


def patient_entry_html(e: PatientEntryOut) -> str:
    label, ic = ENTRY_TYPE_STYLE.get(e.entry_type, ("Information", "info"))
    return f"""
      <div style="display:flex;gap:.75rem;align-items:flex-start;padding:.55rem 0;border-bottom:1px solid var(--hb-border)">
        {tile_html(ic, "violet", 34, 18)}
        <div style="flex:1"><div style="display:flex;justify-content:space-between;gap:.4rem;align-items:center">
          <span style="font-weight:600;font-size:.88rem">{esc(e.title)}</span>{patient_provided_badge_html()}</div>
          <div style="font-size:.8rem;color:var(--hb-navy-600);margin-top:.15rem">{esc(e.details)}</div>
          <div style="font-size:.72rem;color:var(--hb-muted);margin-top:.15rem">{esc(label)} · {esc(fmt_date(e.created_at))}</div></div></div>"""


def invoice_items_html(inv: InvoiceOut) -> str:
    rows = "".join(f"<tr><td>{esc(i['description'])}</td><td>{i['quantity']}</td><td>{i['unit_price']:,.2f}</td>"
                   f"<td class='strong'>{i['total']:,.2f}</td></tr>" for i in inv.items)
    return ('<table class="hb-table"><thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Total</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>")


FLAG_LABEL = {"high": ("Higher than normal", "coral"), "low": ("Lower than normal", "blue"), "normal": ("Normal", "teal")}


def lab_values_table_html(o: LabOrderOut, plain: bool = False) -> str:
    if not o.values:
        return ""
    rows = []
    for v in o.values:
        label, tone = FLAG_LABEL.get(v.flag, (v.flag.title(), "neutral"))
        flag = badge_html(label if plain else v.flag.title(), tone)
        rows.append(f"<tr><td class='strong'>{esc(v.analyte)}</td><td><b>{esc(v.value)}</b> "
                    f"<span class='muted'>{esc(v.unit)}</span></td><td class='muted'>{esc(v.reference)}</td><td>{flag}</td></tr>")
    return ('<div class="hb-table-wrap" style="margin-top:.7rem"><table class="hb-table"><thead><tr>'
            '<th>Test</th><th>Result</th><th>Reference</th><th></th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def lab_report_card_html(o: LabOrderOut, show_patient: bool = False, plain: bool = False, show_values: bool = True) -> str:
    title = f"{o.patient.name}" if show_patient else o.test_name
    sub = f"{o.display_id} · {o.test_name}" if show_patient else f"{o.display_id} · ordered by {o.provider_name}"
    when = o.published_at or o.ordered_at
    prio = badge_html("Urgent", "coral", "priority_high") if o.priority == "urgent" else ""
    interp = (f'<div style="font-size:.84rem;margin-top:.6rem;color:var(--hb-navy-600)">{esc(o.interpretation)}</div>'
              if o.interpretation and show_values else "")
    return f"""
      <div class="hb-rx">
        <div class="head"><div class="title">{esc(title)}</div><span>{prio} {lab_status_badge_html(o.status)}</span></div>
        <div class="sub">{esc(sub)}</div>
        <div style="margin-top:.45rem;display:flex;gap:.35rem;flex-wrap:wrap">
          {org_badge_html(o.organization_name, o.organization_type)}{org_badge_html(o.lab_name, "laboratory")}</div>
        {lab_values_table_html(o, plain) if show_values else ""}{interp}
        <div class="foot"><span>{icon("science" if o.test_category == "lab" else "radiology", 14)} {esc(o.test_category.title())}</span>
          <span>{icon("schedule", 14)} {esc(fmt_when(when))}</span></div>
      </div>"""


def lab_report_card(o: LabOrderOut, **kw) -> None:
    html(f'<div class="hb-card">{lab_report_card_html(o, **kw)}</div>')


EVENT_STYLE = {
    "consultation": ("Consultation", "stethoscope", "teal"),
    "clinical_note": ("Doctor's note", "clinical_notes", "teal"),
    "prescription_issued": ("Prescription", "prescriptions", "blue"),
    "prescription_sent": ("Sent to pharmacy", "send", "blue"),
    "prescription_verified": ("Verified by pharmacy", "fact_check", "amber"),
    "prescription_rejected": ("Prescription rejected", "block", "coral"),
    "prescription_cancelled": ("Prescription cancelled", "cancel", "neutral"),
    "dispensing": ("Medicine dispensed", "local_pharmacy", "teal"),
    "invoice_issued": ("Invoice", "receipt_long", "amber"),
    "lab_ordered": ("Test ordered", "biotech", "navy"),
    "lab_report_published": ("Lab report published", "lab_profile", "teal"),
    "document_added": ("Document added", "description", "navy"),
    "patient_entry": ("Added by you", "person_edit", "violet"),
}

# Spec'd timeline filters: All · Consultations · Prescriptions · Labs · Hospital · Pharmacy · Documents
TIMELINE_FILTERS = ["All", "Consultations", "Prescriptions", "Labs", "Hospital", "Pharmacy", "Documents"]


# Which consent categories make each filter meaningful for a doctor.
FILTER_CATEGORIES = {"Consultations": ("consultations",), "Prescriptions": ("prescriptions",),
                     "Labs": ("lab_reports", "imaging_reports"), "Hospital": ("hospital_records",),
                     "Pharmacy": ("prescriptions",), "Documents": ("documents",)}


def authorized_filters(access) -> tuple[list[str], list[str]]:
    """(filters to offer, filters locked by consent). The patient's own view gets every filter."""
    if access is None or access.via == "self":
        return list(TIMELINE_FILTERS), []
    allowed = [f for f in TIMELINE_FILTERS[1:] if any(access.can(c) for c in FILTER_CATEGORIES[f])]
    return ["All", *allowed], [f for f in TIMELINE_FILTERS[1:] if f not in allowed]


def timeline_group(e: TimelineEventOut) -> str:
    if e.record_category == "hospital_records":
        return "Hospital"
    if e.event_type in ("prescription_verified", "prescription_rejected", "dispensing", "invoice_issued"):
        return "Pharmacy"
    if e.event_type in ("prescription_issued", "prescription_sent", "prescription_cancelled"):
        return "Prescriptions"
    if e.event_type in ("lab_ordered", "lab_report_published") or e.record_category in ("lab_reports", "imaging_reports"):
        return "Labs"
    if e.event_type in ("document_added", "patient_entry"):
        return "Documents"
    return "Consultations"


MEDICATION_EVENTS = ("prescription_issued", "prescription_verified", "dispensing")


def timeline_matches(e: TimelineEventOut, choice: str | None) -> bool:
    if not choice or choice == "All":
        return True
    if choice == "Medications":  # doctor view: medication history (prescribed → verified → dispensed)
        return e.event_type in MEDICATION_EVENTS
    return timeline_group(e) == choice


def filter_timeline(events: Sequence[TimelineEventOut], choice: str | None) -> list[TimelineEventOut]:
    return [e for e in events if timeline_matches(e, choice)]


def consultation_list_html(c) -> str:
    """Compact consultation row: date, organization, doctor, reason, assessment/diagnosis, status."""
    status = badge_html("Draft", "amber", "edit_note") if c.status == "draft" else badge_html("Final", "teal", "verified")
    dx = c.diagnosis or c.assessment
    return f"""
      <div style="display:flex;justify-content:space-between;gap:.75rem;align-items:flex-start;flex-wrap:wrap">
        <div style="min-width:0;flex:1"><div style="font-weight:700">{esc(c.complaint or "Untitled draft")}</div>
          <div style="font-size:.82rem;color:var(--hb-navy-600);margin-top:.15rem">{esc(dx) if dx else '<span style="color:var(--hb-muted)">No assessment yet</span>'}</div>
          <div style="margin-top:.4rem;display:flex;gap:.4rem;align-items:center;flex-wrap:wrap">
            {org_badge_html(c.organization_name, c.organization_type)}
            <span style="font-size:.76rem;color:var(--hb-muted)">{icon("person", 14)} {esc(c.provider_name)} · {esc(c.patient_name)}</span></div></div>
        <div style="text-align:right">{status}<div style="font-size:.76rem;color:var(--hb-muted);margin-top:.35rem">{esc(fmt_when(c.updated_at if c.status == "draft" and c.updated_at else c.date))}</div></div>
      </div>"""


def timeline(events: Sequence[TimelineEventOut], group_by_day: bool = True, empty_body: str | None = None) -> None:
    """Vertical, newest-first longitudinal timeline. Each entry keeps its organization context."""
    if not events:
        empty_state("No timeline events", empty_body or "Consultations, prescriptions, tests and dispensing appear here.",
                    "timeline", boxed=False)
        return
    parts, last_day = [], None
    for e in events:
        day = fmt_date(e.occurred_at)
        if group_by_day and day != last_day:
            parts.append(f'<div class="hb-tl-day">{esc(day)}</div>')
            last_day = day
        title, ic, tone = EVENT_STYLE.get(e.event_type, (e.event_type.replace("_", " ").title(), "event", "neutral"))
        person = e.actor_name if e.source_type == "provider" else None
        src = source_html(e.source_type, e.organization_name, e.organization_type, person)
        when = fmt_time(e.occurred_at) if group_by_day else fmt_when(e.occurred_at)
        internal = "" if e.patient_visible else badge_html("Internal · clinicians only", "coral", "visibility_off")
        parts.append(f"""
          <div class="hb-tl-item">
            <div class="hb-tl-dot tone-{tone}">{icon(ic, 20)}</div>
            <div class="hb-tl-body">
              <div class="hb-tl-top"><span class="hb-tl-title">{esc(title)}</span><span class="hb-tl-when">{esc(when)}</span></div>
              <div class="hb-tl-text">{esc(e.summary)}</div>
              <div class="hb-tl-meta"><span class="hb-src-lbl">Source</span>{src}{internal}</div>
            </div>
          </div>""")
    html(f'<div class="hb-timeline">{"".join(parts)}</div>')


def care_network_diagram(patient_name: str, nodes: Sequence[tuple[str, str, str]], records: int) -> None:
    """'One patient. One longitudinal timeline. Many connected providers.'

    nodes: (name, org_type or 'doctor', subtitle).
    """
    items = []
    for name, kind, subtitle in nodes:
        if kind == "doctor":
            ic, tone, label = "person", "teal", "Doctor"
        else:
            label, ic, tone = ORG_STYLE.get(kind, (kind.title(), "domain", "neutral"))
        items.append(f"""
          <div class="hb-net-node"><span class="hb-tile tone-{tone}" style="width:38px;height:38px">{icon(ic, 20)}</span>
            <div class="nm">{esc(name)}</div><div class="sb">{esc(label)} · {esc(subtitle)}</div></div>""")
    html(f"""
      <div class="hb-net">
        <div class="hb-net-center">{avatar_html(patient_name, 56)}
          <div><div class="hb-net-title">{esc(patient_name)}</div>
            <div class="hb-net-sub">{icon("timeline", 16)} One longitudinal HealthBridge timeline · {plural(records, "record")}</div></div>
        </div>
        <div class="hb-net-rail"></div>
        <div class="hb-net-nodes">{"".join(items)}</div>
      </div>""")
