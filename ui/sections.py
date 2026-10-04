"""Composite, page-level sections built from ui.components. Shared by several pages."""

from collections.abc import Sequence

import streamlit as st

from core.models import RecordCategory
from core.schemas import (
    AIFlagOut,
    AuthorizedRecord,
    ClinicalNoteOut,
    CareNetwork,
    ConsultationOut,
    DirectoryEntry,
    MedicationOut,
    PrescriptionOut,
)
from ui.components import (
    ORG_STYLE,
    access_status_html,
    ai_badge_html,
    alert_card,
    allergy_chips_html,
    avatar_html,
    badge_html,
    category_chips_html,
    condition_chips_html,
    data_table,
    empty_state,
    esc,
    fmt_ago,
    fmt_date,
    fmt_when,
    html,
    icon,
    lab_report_card,
    org_badge_html,
    patient_identity_html,
    plural,
    section_header,
    authorized_filters,
    document_card_html,
    filter_timeline,
    patient_entry_html,
    provider_card_html,
    severity_badge_html,
    status_badge_html,
    tile_html,
    timeline,
    timeline_matches,
    verified_badge_html,
)


def medications_html(meds: Sequence[MedicationOut], compact: bool = False, empty: str = "No current medications") -> str:
    if not meds:
        return f'<span class="hb-chip tone-neutral">{esc(empty)}</span>'
    rows = []
    for m in meds:
        detail = m.frequency if compact else f"{m.frequency} · until {fmt_date(m.ends)}"
        rows.append(f"""
          <div style="display:flex;gap:.6rem;align-items:center;margin-bottom:.45rem">{tile_html("pill", "teal", 28, 16)}
            <div style="line-height:1.25"><div style="font-weight:600;font-size:.86rem">{esc(m.drug_name)} {esc(m.strength)}</div>
            <div style="font-size:.76rem;color:var(--hb-muted)">{esc(detail)}</div></div>
          </div>""")
    return "".join(rows)


def patient_hero(record: AuthorizedRecord, right_badge: str = "") -> None:
    """Profile header: identity, allergies, conditions, current medications."""
    p = record.patient
    last = fmt_ago(record.timeline[0].occurred_at) if record.timeline else "No activity yet"
    meds = [m for m in record.medications if m.current]
    meds_html = (medications_html(meds, compact=True) if record.access.can(RecordCategory.MEDICATIONS)
                 else f'<span class="hb-chip tone-neutral">{icon("lock", 14)}Not shared with you</span>')
    html(f"""
      <div class="hb-card">
        <div class="hb-hero">{avatar_html(p.name, 64)}
          <div style="flex:1;min-width:220px">
            <div class="name">{esc(p.name)}</div>
            <div class="meta">
              <span>{icon("cake", 16)} {p.age} years</span><span>{icon("person", 16)} {esc(p.sex.title())}</span>
              <span>{icon("badge", 16)} {esc(p.display_id)}</span><span>{icon("history", 16)} Last activity {esc(last)}</span>
            </div>
          </div>
          <div>{right_badge}</div>
        </div>
        <div class="hb-hero-grid">
          <div><div class="lbl">Allergies</div>{allergy_chips_html(p.allergies)}</div>
          <div><div class="lbl">Conditions</div>{condition_chips_html(p.conditions)}</div>
          <div><div class="lbl">Current medications</div>{meds_html}</div>
        </div>
      </div>""")


def consultation_card(c: ConsultationOut, title: str = "Most recent consultation") -> None:
    fields = [("Symptoms / notes", c.notes), ("Observations", c.observations), ("Assessment", c.assessment),
              ("Diagnosis", c.diagnosis), ("Treatment plan", c.treatment_plan), ("Follow-up", c.follow_up),
              ("Additional notes", c.additional_notes)]   # patient-visible; internal clinician notes are never here
    rows = "".join(f'<span class="k">{esc(k)}</span><span class="v">{esc(v)}</span>' for k, v in fields if v)
    html(f"""
      <div class="hb-card">
        <div class="hb-section" style="margin-top:0"><h3>{esc(title)}</h3><span class="hint">{esc(fmt_when(c.date))}</span></div>
        <div style="font-weight:600">{esc(c.complaint)}</div>
        <div style="margin:.35rem 0 .7rem;display:flex;gap:.4rem;align-items:center;flex-wrap:wrap">
          {org_badge_html(c.organization_name, c.organization_type)}<span style="font-size:.8rem;color:var(--hb-muted)">{esc(c.provider_name)}</span></div>
        <div class="hb-kv">{rows}</div>
      </div>""")


NOTE_LABELS = {"consultation": "Consultation note", "follow_up": "Follow-up note", "observation": "Clinical observation",
               "internal": "Internal clinical note"}


def note_badge_html(n: ClinicalNoteOut) -> str:
    """Patient-visible clinical record vs internal clinician note."""
    if n.note_type == "internal":
        return badge_html("Internal note · not visible to patient", "coral", "visibility_off")
    return badge_html(NOTE_LABELS.get(n.note_type, "Note"), "teal", "clinical_notes")


def notes_list_html(notes: Sequence[ClinicalNoteOut]) -> str:
    return "".join(f"""
      <div style="padding:.65rem 0;border-bottom:1px solid var(--hb-border)">
        <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center;flex-wrap:wrap">
          <span>{note_badge_html(n)}
            <span style="font-size:.78rem;color:var(--hb-navy-600);font-weight:600">Written by {esc(n.provider_name)}</span></span>
          <span style="font-size:.74rem;color:var(--hb-muted)">{esc(fmt_when(n.created_at))}</span></div>
        <div style="font-size:.88rem;margin:.4rem 0">{esc(n.content)}</div>
        <div>{org_badge_html(n.organization_name, n.organization_type)}</div>
      </div>""" for n in notes)


def notes_card(notes: Sequence[ClinicalNoteOut], title: str = "Doctor's notes") -> None:
    rows = "".join(f"""
      <div style="padding:.6rem 0;border-bottom:1px solid var(--hb-border)">
        <div style="display:flex;justify-content:space-between;gap:.5rem;align-items:center">
          {note_badge_html(n)}
          <span style="font-size:.74rem;color:var(--hb-muted)">{esc(fmt_when(n.created_at))}</span></div>
        <div style="font-size:.86rem;margin:.35rem 0">{esc(n.content)}</div>
        <div style="display:flex;gap:.4rem;align-items:center">{org_badge_html(n.organization_name, n.organization_type)}
          <span style="font-size:.76rem;color:var(--hb-muted)">{esc(n.provider_name)}</span></div>
      </div>""" for n in notes)
    html(f"""<div class="hb-card"><div class="hb-section" style="margin-top:0"><h3>{esc(title)}</h3>
             {verified_badge_html("Clinician-authored · never edited by AI")}</div>{rows or '<div style="font-size:.85rem;color:var(--hb-muted)">No notes yet.</div>'}</div>""")


def consultations_table(rows: Sequence[ConsultationOut], show_patient: bool = True, empty: str = "No consultations") -> None:
    headers = (["When", "Patient"] if show_patient else ["When"]) + ["Reason / assessment", "Organization", "Doctor"]
    data_table(headers, [
        [f'<span class="strong">{esc(fmt_when(c.date))}</span>']
        + ([f'<span class="strong">{esc(c.patient_name)}</span>'] if show_patient else [])
        + [f'{esc(c.complaint)}<div class="muted">{esc(c.assessment)}</div>',
           org_badge_html(c.organization_name, c.organization_type), esc(c.provider_name)]
        for c in rows], empty=empty)


def prescription_history(rxs: Sequence[PrescriptionOut]) -> None:
    rows = [[
        f'<span class="strong">{esc(rx.display_id)}</span><div class="muted">{esc(fmt_date(rx.created_at))}</div>',
        "<br>".join(f'<span class="strong">{esc(i.drug_name)} {esc(i.strength)}</span> '
                    f'<span class="muted">{esc(i.frequency)}</span>' for i in rx.items),
        f'{esc(rx.provider_name)}<div style="margin-top:.25rem">{org_badge_html(rx.organization_name, rx.organization_type)}</div>',
        esc(rx.pharmacy_name or "—"),
        status_badge_html(rx.status),
    ] for rx in rxs]
    data_table(["Prescription", "Medication", "Prescriber", "Pharmacy", "Status"], rows, empty="No prescriptions")


def flag_card(f: AIFlagOut) -> None:
    html(f"""
      <div class="hb-card hb-ai-card">
        <div style="display:flex;justify-content:space-between;gap:.5rem;flex-wrap:wrap">{ai_badge_html()}{severity_badge_html(f.severity)}</div>
        <div style="font-weight:600;margin-top:.6rem">{esc(f.message)}</div>
        <div style="font-size:.78rem;color:var(--hb-muted);margin-top:.3rem">{esc(f.patient_name)} · {esc(f.category.replace("_", " "))} · {esc(fmt_when(f.created_at))}</div>
      </div>""")


# ---------------------------------------------------------------------------
# Doctor: consent-aware patient views
# ---------------------------------------------------------------------------


def not_shared(record: AuthorizedRecord) -> list[str]:
    return [c.value for c in RecordCategory if not record.access.can(c)]


def access_banner(record: AuthorizedRecord, organization_name: str | None) -> None:
    hidden = not_shared(record)
    extra = (f'<div class="s" style="margin-top:.45rem">Not shared with you: {category_chips_html(hidden, "neutral", locked=True)}</div>'
             if hidden else "")
    html(access_status_html(record.access, organization_name, extra=extra))


def authorized_record_view(record: AuthorizedRecord, organization_name: str | None) -> None:
    """The record exactly as consented: banner, hero, timeline and each shared category."""
    access_banner(record, organization_name)
    patient_hero(record, right_badge=badge_html("Consent-based view", "teal", "verified_user"))
    left, right = st.columns([3, 2], gap="large")
    with left:
        timeline_with_filters(record.timeline, key="rec_tl",
                              title=f"Medical timeline · {plural(len(record.timeline), 'record')} you may see")
    with right:
        if record.consultations:
            consultation_card(record.consultations[0])
        if record.notes:
            notes_card(record.notes[:3])
        section_header("Reports")
        if record.reports:
            for o in record.reports[:3]:
                lab_report_card(o)
        elif record.access.can(RecordCategory.LAB_REPORTS) or record.access.can(RecordCategory.IMAGING_REPORTS):
            empty_state("No reports yet", icon_name="biotech")
        else:
            alert_card("Reports not shared", "The patient has not shared laboratory or imaging reports with you.", "lock")
    if record.access.can(RecordCategory.PRESCRIPTIONS):
        section_header("Prescription history", plural(len(record.prescriptions), "prescription"))
        prescription_history(record.prescriptions)
    if record.access.can(RecordCategory.DOCUMENTS):
        section_header("Documents & patient-provided information")
        cols = st.columns(3)
        for i, d in enumerate(record.documents):
            with cols[i % 3]:
                html(f'<div class="hb-card">{document_card_html(d)}</div>')
        if record.patient_entries:
            html('<div class="hb-card" style="padding-top:.4rem">' + "".join(map(patient_entry_html, record.patient_entries)) + "</div>")


def timeline_with_filters(events, key: str, title: str = "Medical timeline", filters=None, access=None) -> None:
    """Timeline with filters: All · Consultations · Prescriptions · Labs · Hospital · Pharmacy · Documents.

    With a doctor's `access`, only filters for consented categories are offered (the events themselves are
    already filtered by record_service); the rest are listed as not shared.
    """
    locked: list[str] = []
    if filters is None:
        filters, locked = authorized_filters(access)
    counts = {f: sum(timeline_matches(e, f) for e in events) for f in filters}
    section_header(title, "Newest first · every entry shows its source")
    if locked:
        html(f'<div style="font-size:.78rem;color:var(--hb-muted);margin:-.3rem 0 .4rem">{icon("lock", 13)} Not shared with '
             f'you: {esc(" · ".join(locked))}</div>')
    choice = st.segmented_control("Filter", filters, default="All", required=True, key=key,
                                  label_visibility="collapsed", format_func=lambda f: f"{f} ({counts[f]})")
    with st.container(key=f"hbcard_{key}"):
        timeline(filter_timeline(events, choice), empty_body="No records in the categories shared with you.")


def locked_patient_view(entry: DirectoryEntry, organization_name: str | None) -> None:
    html(f'<div class="hb-card">{patient_identity_html(entry.patient, size=56)}</div>')
    alert_card("Records unavailable",
               "Patient consent is required to access this patient's HealthBridge records. "
               f"Ask {entry.patient.name.split()[0]} to share their records with you"
               f"{' at ' + organization_name if organization_name else ''} from their HealthBridge app.", "lock")


# ---------------------------------------------------------------------------
# Patient: care network
# ---------------------------------------------------------------------------


def access_label(doctor) -> str:
    active = [c for c in doctor.consents if c.active]
    if active:
        return " ".join(badge_html(f"{'All' if c.scope_type == 'all' else 'Selected'} · {c.organization_name}", "teal", "check_circle")
                        for c in active)
    if doctor.consents:
        return badge_html("Access ended", "neutral", "block")
    return badge_html("No access to your records", "neutral", "lock")


def care_team_doctors(network: CareNetwork) -> None:
    if not network.doctors:
        empty_state("No doctors yet", icon_name="person")
        return
    cols = st.columns(min(3, len(network.doctors)))
    for i, d in enumerate(network.doctors):
        with cols[i % len(cols)]:
            html(f'<div class="hb-card">{provider_card_html(d.name, d.specialty, d.organizations, extra=f"<div style=margin-top:.6rem>{access_label(d)}</div>")}</div>')


ORG_PLURALS = {"clinic": "Clinics", "hospital": "Hospitals", "laboratory": "Laboratories", "pharmacy": "Pharmacies"}


def care_team_organizations(network: CareNetwork) -> None:
    cols = st.columns(4)
    for col, kind in zip(cols, ["clinic", "hospital", "laboratory", "pharmacy"]):
        label, ic, tone = ORG_STYLE[kind]
        orgs = [o for o in network.organizations if o.organization.org_type == kind]
        rows = "".join(f"""
          <div style="padding:.55rem 0;border-top:1px solid var(--hb-border)">
            <div style="font-weight:600;font-size:.86rem">{esc(o.organization.name)}</div>
            <div style="font-size:.75rem;color:var(--hb-muted)">{esc(o.relation)}{' · ' + esc(fmt_date(o.last_seen)) if o.last_seen else ''}</div></div>"""
                       for o in orgs) or '<div style="font-size:.8rem;color:var(--hb-muted);padding-top:.5rem">None yet</div>'
        with col:
            html(f"""<div class="hb-card"><div style="display:flex;align-items:center;gap:.55rem;margin-bottom:.5rem">
                     {tile_html(ic, tone)}<span style="font-weight:700">{ORG_PLURALS[kind]}</span></div>{rows}</div>""")
