"""Regressions for issues found in the Phase 2 browser walkthrough (real Streamlit pages via AppTest).

1. Visit date/time chosen by the doctor survives reruns and the clock moving on before Save.
2. Opening a patient found via the top-bar search keeps them selected for New consultation.
3. The share dialog lists each doctor's primary organization first (Dr. Arif → South City Hospital).
4. The access-restricted hint points to the "Working at" selector in the top bar.
5. Recent patients labels "Last visit" separately from "Access" at the current organization.
6. Additional notes are visible to the patient; internal clinician notes are not (service + UI).
"""

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from core.config import ROOT_DIR
from core.db import get_session
from core.models import Consultation, Organization, Prescription, Role, User
from services import clinical_service, consent_service, record_service, user_service
from services.clinical_service import ConsultationInput
from ui import components
from ui.components import to_local

APP = str(ROOT_DIR / "app.py")
AYESHA, AHMED_PATIENT = 1, 1                     # Dr. Ayesha Malik (all-records consent) · Ahmed Khan (patient 1)


def start(role=Role.DOCTOR, user_id=AYESHA, org_id=None, page=None, **state) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["hb_entered"], at.session_state["hb_role"], at.session_state["hb_user_id"] = True, role, user_id
    if org_id:
        at.session_state["hb_org_id"] = org_id
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    if page:
        at.switch_page(page)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def markup(at) -> str:
    return " ".join(m.value for m in at.markdown)


def ids(name: str) -> int:
    with get_session() as s:
        return s.scalar(select(User.id).where(User.name == name))


def org_id(name: str) -> int:
    with get_session() as s:
        return s.scalar(select(Organization.id).where(Organization.name == name))


# 1. Visit time ------------------------------------------------------------------------------------


def test_selected_visit_time_survives_rerun_and_clock_change_and_reaches_the_prescription(monkeypatch):
    real_now = components.local_now()
    at = start(page="views/doctor/consultation_editor.py", sel_patient=AHMED_PATIENT)
    # The page reruns after the clock has moved to a later minute: initial values must not be recomputed.
    monkeypatch.setattr(components, "local_now", lambda: real_now + timedelta(minutes=3))
    at.run()
    chosen_date = (real_now - timedelta(days=1)).date()
    next(w for w in at.date_input if w.label == "Visit date").set_value(chosen_date)
    next(w for w in at.time_input if w.label == "Visit time").set_value(time(10, 15))
    next(t for t in at.text_input if t.label == "Reason for visit *").set_value("REGRESSION: visit time")
    next(t for t in at.text_area if t.label == "Assessment").set_value("Checked")
    # ...and moves on again before the doctor clicks Save (the original bug: the submitted time was replaced).
    monkeypatch.setattr(components, "local_now", lambda: real_now + timedelta(minutes=7))
    next(b for b in at.button if b.label == "Save & create prescription").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    with get_session() as s:
        c = s.scalar(select(Consultation).where(Consultation.complaint == "REGRESSION: visit time"))
        saved = to_local(c.date)
        cid = c.id
    assert (saved.date(), saved.time().replace(tzinfo=None)) == (chosen_date, time(10, 15))

    # The prescription form opened linked to it; issue it and check the linked consultation's time.
    assert at.session_state["rx_consultation"] == cid
    at.switch_page("views/doctor/prescription_editor.py")   # AppTest: follow the script's page switch
    at.run()
    next(s for s in at.selectbox if s.label == "Medicine name *").set_value("Metformin")
    next(t for t in at.text_input if t.label == "Strength *").set_value("500 mg")
    next(t for t in at.text_input if t.label == "Frequency *").set_value("twice daily")
    next(n for n in at.number_input if n.label == "Duration (days) *").set_value(30)
    next(n for n in at.number_input if n.label == "Quantity *").set_value(60)
    next(b for b in at.button if b.label == "Issue Prescription").click()
    at.run()
    [b for b in at.button if b.label == "Issue Prescription"][-1].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    with get_session() as s:
        rx = s.scalar(select(Prescription).where(Prescription.consultation_id == cid))
        linked = to_local(rx.consultation.date)
    assert (linked.date(), linked.hour, linked.minute) == (chosen_date, 10, 15)
    assert components.fmt_datetime(rx.consultation.date).endswith("10:15")
    assert components.fmt_datetime(rx.consultation.date) in markup(at)   # shown on the prescription page


def test_new_consultation_starts_from_now_not_a_previous_forms_time():
    at = start(page="views/doctor/consultation_editor.py", sel_patient=AHMED_PATIENT,
               ce_visit_for="new-999", ce_visit_date=date(2026, 1, 1), ce_visit_time=time(3, 0),
               ce_visit_max=date(2026, 1, 1))
    assert at.date_input(key="ce_visit_date").value == datetime.now().date()   # stale state for another form ignored


# 2. Top-bar search → workspace → New consultation ----------------------------------------------------


def test_top_bar_search_then_open_patient_keeps_selection_for_new_consultation():
    at = start(page="views/doctor/dashboard.py")
    at.text_input(key="hb_search").set_value("Ahmed").run()          # flow A: top-bar search
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["pt_q"] == "Ahmed" and "1 patient" in markup(at)
    # AppTest does not keep a script-initiated page switch for the next run (a browser does, via the URL),
    # so mirror each navigation explicitly.
    at.switch_page("views/doctor/patients.py")
    at.run()
    next(b for b in at.button if b.label == "Open Patient").click()
    at.run()
    assert at.session_state["sel_patient"] == AHMED_PATIENT
    assert at.text_input(key="hb_search").value == ""                 # search cleared once the patient is open
    assert "Patient has granted you access" in markup(at)
    at.run()                                                          # navigation reruns keep the selection
    next(b for b in at.button if b.label == "New consultation").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="ce_patient").value == AHMED_PATIENT
    assert any(t.label == "Reason for visit *" for t in at.text_input)


def test_patient_list_then_open_patient_then_new_consultation():
    at = start(page="views/doctor/patients.py")                      # flow B: Patients page search
    at.text_input(key="pt_q").set_value("Ahmed").run()
    next(b for b in at.button if b.label == "Open Patient").click()
    at.run()
    next(b for b in at.button if b.label == "New consultation").click()
    at.run()
    assert at.selectbox(key="ce_patient").value == AHMED_PATIENT


def test_clearing_the_top_bar_search_does_not_close_the_open_patient():
    at = start(page="views/doctor/patients.py", sel_patient=AHMED_PATIENT)
    at.text_input(key="hb_search").set_value("").run()
    assert at.session_state["sel_patient"] == AHMED_PATIENT


# 3. Share dialog default --------------------------------------------------------------------------


def test_share_dialog_defaults_to_dr_arif_at_south_city_hospital():
    at = start(role=Role.PATIENT, user_id=ids("Ahmed Khan"), page="views/patient/consent.py")
    next(b for b in at.button if b.label == "Share Records with a Doctor").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    pick = at.selectbox(key="share_pick")
    assert pick.format_func(pick.value) == "Dr. Arif Hassan — South City Hospital"
    assert "Dr. Arif Hassan — Clifton Medical Centre" in pick.options   # other organization still selectable


def test_provider_options_list_primary_organization_first(seeded):
    names = [(o.provider_name, o.organization_name) for o in consent_service.search_providers(seeded)]
    assert names.index(("Dr. Arif Hassan", "South City Hospital")) < names.index(("Dr. Arif Hassan", "Clifton Medical Centre"))
    assert len(names) == 6                                               # nothing removed


# 4. Organization-switching wording -----------------------------------------------------------------


@pytest.fixture
def arif_consent_at_south_city():
    with get_session() as s:
        ahmed = user_service.make_actor(s, ids("Ahmed Khan"))
        consent = consent_service.grant(s, ahmed, provider_id=ids("Dr. Arif Hassan"), organization_id=org_id("South City Hospital"),
                                        scope_type="selected", categories=["consultations", "prescriptions", "medications"])
    yield
    with get_session() as s:
        consent_service.revoke(s, user_service.make_actor(s, ids("Ahmed Khan")), consent.id)


def test_restricted_banner_points_to_working_at_selector(arif_consent_at_south_city):
    at = start(user_id=ids("Dr. Arif Hassan"), org_id=org_id("Clifton Medical Centre"), page="views/doctor/patients.py",
               sel_patient=AHMED_PATIENT)
    html = markup(at)
    assert "ACCESS RESTRICTED" in html and "South City Hospital" in html
    assert "switch organization using the “Working at” selector in the top bar." in html
    assert "profile menu" not in html


# 5. Recent patients labels -------------------------------------------------------------------------


def test_recent_patients_label_last_visit_and_access_separately(arif_consent_at_south_city):
    at = start(user_id=ids("Dr. Arif Hassan"), org_id=org_id("South City Hospital"), page="views/doctor/dashboard.py")
    html = markup(at)
    assert "Recent patients" in html and "Last visit" in html and "Access" in html
    assert "Granted at South City Hospital" in html
    at = start(user_id=ids("Dr. Arif Hassan"), org_id=org_id("Clifton Medical Centre"), page="views/doctor/dashboard.py")
    assert "Not granted at Clifton Medical Centre" in markup(at) or "Granted at Clifton Medical Centre" in markup(at)


# 6. Additional notes vs internal notes ---------------------------------------------------------------


def test_additional_notes_visible_to_patient_internal_note_hidden(seeded, actor, pid):
    """Service / data-access layer."""
    ayesha = actor("Dr. Ayesha Malik")
    c = clinical_service.save_consultation(seeded, ayesha, pid("Ahmed Khan"), ConsultationInput(
        complaint="Svc visit", assessment="x", additional_notes="Drink plenty of fluids."), finalize=True)
    clinical_service.add_note(seeded, ayesha, pid("Ahmed Khan"), "internal", "SVC-INTERNAL do not show", consultation_id=c.id)
    own = record_service.own_record(seeded, actor("Ahmed Khan"))
    mine = next(x for x in own.consultations if x.id == c.id)
    assert mine.additional_notes == "Drink plenty of fluids."
    assert all("SVC-INTERNAL" not in n.content for n in own.notes)
    assert "SVC-INTERNAL" not in own.model_dump_json()


def test_patient_sees_additional_notes_but_not_internal_note_in_ui():
    with get_session() as s:
        ayesha = user_service.make_actor(s, AYESHA)
        c = clinical_service.save_consultation(s, ayesha, AHMED_PATIENT, ConsultationInput(
            complaint="UI additional-notes visit", assessment="Reviewed", additional_notes="UI-ADDITIONAL: rest for two days."),
            finalize=True)
        clinical_service.add_note(s, ayesha, AHMED_PATIENT, "internal", "UI-INTERNAL: clinicians only", consultation_id=c.id)
    at = start(role=Role.PATIENT, user_id=ids("Ahmed Khan"), page="views/patient/my_health.py")
    html = markup(at)
    assert "Additional notes" in html and "UI-ADDITIONAL: rest for two days." in html
    assert "UI-INTERNAL" not in html
    for path in ("views/patient/home.py", "views/patient/timeline.py"):
        at.switch_page(path)
        at.run()
        assert not at.exception and "UI-INTERNAL" not in markup(at)
