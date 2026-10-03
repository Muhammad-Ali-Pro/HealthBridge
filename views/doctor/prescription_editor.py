import uuid

import streamlit as st

from core.db import get_session
from data.catalog import drug_names
from services import access_service, patient_service, prescription_service
from services.clinical_service import ClinicalValidationError
from services.prescription_service import ROUTES, MedicineInput
from ui import doctor
from ui.components import alert_card, allergy_chips_html, data_table, esc, fmt_date, html, icon, org_badge_html, page_header
from ui.shell import current_actor

actor = current_actor()
ss = st.session_state
rx_id = ss.get("sel_rx_edit")
errors: dict[str, str] = ss.get("rx_errors", {})
FIELDS = ("drug_name", "strength", "dosage", "route", "frequency", "duration_days", "quantity", "instructions")

if st.button("Back", icon=":material/arrow_back:", type="tertiary", key="pe_back"):
    ss.pop("rx_errors", None)
    st.switch_page(doctor.PATIENTS if ss.get("sel_patient") else "views/doctor/prescriptions.py")
page_header("Continue draft prescription" if rx_id else "New prescription",
            "Prescribing doctor, organization and date are captured automatically.", eyebrow="Prescriptions")

# --- Patient --------------------------------------------------------------------------------------
draft = None
if rx_id:
    with get_session() as s:
        draft = prescription_service.get_prescription(s, actor, rx_id)
    patient_id = draft.patient_id
else:
    with st.container(key="hbform_rx_patient"):
        patient_id = doctor.pick_patient(actor, key="pe_patient")
if not patient_id:
    st.stop()

with get_session() as s:
    decision = access_service.authorize(s, actor, patient_id)
    identity = next(e.patient for e in patient_service.directory(s, actor) if e.patient.id == patient_id)
    if decision.allowed:
        allergies = prescription_service.patient_allergies(s, actor, patient_id)
        consultations = prescription_service.patient_consultations(s, actor, patient_id)
if not decision.allowed:
    doctor.consent_banner(actor, decision, identity.name)
    st.stop()

# --- Medicine rows (session-state backed) ----------------------------------------------------------
loaded_for = f"{patient_id}:{rx_id}"
if ss.get("rx_loaded_for") != loaded_for or "rx_rows" not in ss:
    ss["rx_loaded_for"] = loaded_for
    ss["rx_rows"] = []
    for item in (draft.items if draft else [None]):
        uid = uuid.uuid4().hex[:8]
        ss["rx_rows"].append(uid)
        src = item.model_dump() if item else MedicineInput().model_dump()
        for f in FIELDS:
            ss[f"rx_{uid}_{f}"] = (src[f] or None) if f == "drug_name" else src[f]
    ss["rx_notes"] = draft.notes if draft else ""
    ss["rx_consultation"] = draft.consultation_id if draft else ss.get("sel_rx_consultation")


def add_row() -> None:
    uid = uuid.uuid4().hex[:8]
    ss["rx_rows"].append(uid)
    ss[f"rx_{uid}_route"] = "oral"


def remove_row(uid: str) -> None:
    ss["rx_rows"].remove(uid)


def collect() -> list[MedicineInput]:
    out = []
    for uid in ss["rx_rows"]:
        v = {f: ss.get(f"rx_{uid}_{f}") for f in FIELDS}
        out.append(MedicineInput(drug_name=v["drug_name"] or "", strength=v["strength"] or "", dosage=v["dosage"] or "",
                                 route=v["route"] or "oral", frequency=v["frequency"] or "",
                                 duration_days=int(v["duration_days"] or 0), quantity=int(v["quantity"] or 0),
                                 instructions=v["instructions"] or ""))
    return out


org = actor.organization
html(f"""<div class="hb-card" style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center">
  <div><div class="hb-form-section">{icon("person", 14)} Patient</div><div style="font-weight:800;font-size:1.05rem">{esc(identity.name)}</div>
    <div style="font-size:.8rem;color:var(--hb-muted)">{esc(identity.display_id)} · {identity.age} yrs · {esc(identity.sex.title())}</div></div>
  <div><div class="hb-form-section">{icon("stethoscope", 14)} Prescribing doctor</div><div style="font-weight:600">{esc(actor.user.name)}</div></div>
  <div><div class="hb-form-section">{icon("domain", 14)} Organization</div>{org_badge_html(org.name, org.org_type)}</div>
  <div><div class="hb-form-section">{icon("today", 14)} Date</div><div style="font-weight:600">{esc(fmt_date(draft.created_at) if draft else "Today")}</div></div>
  <div><div class="hb-form-section">{icon("warning", 14)} Allergies</div>{allergy_chips_html(allergies)}</div>
</div>""")

with st.container(key="hbform_rx_link"):
    ids = [None] + [c.id for c in consultations]
    labels = {None: "Not linked to a consultation"} | {c.id: f"{fmt_date(c.date)} · {c.complaint}" for c in consultations}
    if ss.get("rx_consultation") not in ids:
        ss["rx_consultation"] = None
    st.selectbox("Linked consultation", ids, format_func=labels.__getitem__, key="rx_consultation")

if errors.get("items"):
    alert_card(errors["items"], tone="danger")

catalog = drug_names()
for n, uid in enumerate(ss["rx_rows"]):
    with st.container(key=f"hbform_rx_{uid}"):
        top = st.columns([6, 1], vertical_alignment="bottom")
        top[0].markdown(f'<div class="hb-form-section">{icon("pill", 14)} Medicine {n + 1}</div>', unsafe_allow_html=True)
        if len(ss["rx_rows"]) > 1:
            top[1].button("Remove", key=f"rm_{uid}", on_click=remove_row, args=(uid,), type="tertiary", icon=":material/close:")
        r1 = st.columns([2.2, 1, 1, 1.2])
        name_key = f"rx_{uid}_drug_name"
        current_name = ss.get(name_key)
        options = catalog if current_name in (None, *catalog) else [current_name, *catalog]
        extra = {} if name_key in ss else {"index": None}  # value already in session state → no index
        r1[0].selectbox("Medicine name *", options, key=name_key, accept_new_options=True,
                        placeholder="Search or type a medicine", **extra)
        r1[1].text_input("Strength *", key=f"rx_{uid}_strength", placeholder="500 mg")
        r1[2].text_input("Dosage", key=f"rx_{uid}_dosage", placeholder="1 tablet")
        r1[3].selectbox("Route", ROUTES, key=f"rx_{uid}_route")
        for f in ("drug_name", "strength"):
            doctor.show_errors(errors, f"{n}.{f}")
        r2 = st.columns([2.2, 1, 1, 1.2])
        r2[0].text_input("Frequency *", key=f"rx_{uid}_frequency", placeholder="twice daily")
        r2[1].number_input("Duration (days) *", key=f"rx_{uid}_duration_days", min_value=0, step=1)
        r2[2].number_input("Quantity *", key=f"rx_{uid}_quantity", min_value=0, step=1)
        r2[3].text_input("Instructions", key=f"rx_{uid}_instructions", placeholder="Take with meals")
        for f in ("frequency", "duration_days", "quantity"):
            doctor.show_errors(errors, f"{n}.{f}")

st.button("Add another medicine", icon=":material/add:", on_click=add_row)
with st.container(key="hbform_rx_notes"):
    st.text_area("Notes", key="rx_notes", height=70, placeholder="Notes for the record (optional)")

items = collect()
for w in prescription_service.allergy_warnings(allergies, items):
    alert_card("Possible allergy conflict — verify before issuing", w, "danger", "warning")


def save() -> int | None:
    try:
        with get_session() as s:
            out = prescription_service.save_draft(s, actor, patient_id, collect(), notes=ss.get("rx_notes", ""),
                                                  consultation_id=ss.get("rx_consultation"), prescription_id=rx_id)
        ss["sel_rx_edit"] = out.id
        ss["rx_loaded_for"] = f"{patient_id}:{out.id}"
        return out.id
    except ClinicalValidationError as exc:
        ss["rx_errors"] = exc.errors
        return None


def _dismiss_confirm() -> None:
    ss.pop("rx_confirm", None)


@st.dialog("Issue prescription", width="large", on_dismiss=_dismiss_confirm)
def confirm_issue(prescription_id: int) -> None:
    st.markdown(f"You're about to issue this prescription to **{identity.name}**.")
    html(f"""<div class="hb-kv" style="margin:.4rem 0 .8rem"><span class="k">Doctor</span><span class="v">{esc(actor.user.name)}</span>
         <span class="k">Organization</span><span class="v">{esc(org.name)}</span></div>""")
    data_table(["Medicine", "Strength", "Dosage", "Frequency", "Duration", "Qty"], [[
        f'<span class="strong">{esc(m.drug_name)}</span>', esc(m.strength), esc(m.dosage or "—"), esc(m.frequency),
        f"{m.duration_days} days", str(m.quantity)] for m in collect()])
    st.caption("Once issued, the prescription is added to the patient's timeline and can no longer be edited. "
               "Sending it to a pharmacy happens in Phase 3.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        _dismiss_confirm()
        st.rerun()
    if c2.button("Issue Prescription", type="primary", width="stretch", icon=":material/verified:", key="confirm_issue"):
        _dismiss_confirm()
        try:
            with get_session() as s:
                prescription_service.issue(s, actor, prescription_id)
        except ClinicalValidationError as exc:
            ss["rx_errors"] = exc.errors
            st.rerun()
        for k in ("sel_rx_edit", "rx_rows", "rx_loaded_for", "rx_errors"):
            ss.pop(k, None)
        ss["sel_rx"] = prescription_id
        ss["hb_flash"] = "Prescription issued and added to the patient's timeline."
        st.switch_page(doctor.PRESCRIPTION_DETAIL)


with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
    if st.button("Save draft", icon=":material/save:"):
        if save():
            ss.pop("rx_errors", None)
            ss["hb_flash"] = "Draft prescription saved."
        st.rerun()
    if st.button("Issue Prescription", icon=":material/verified:", type="primary"):
        validation = prescription_service.validate_items(collect())
        if validation:
            ss["rx_errors"] = validation
            st.rerun()
        new_id = save()
        if new_id:
            ss.pop("rx_errors", None)
            ss["rx_confirm"] = new_id

if ss.get("rx_confirm"):
    confirm_issue(ss["rx_confirm"])
