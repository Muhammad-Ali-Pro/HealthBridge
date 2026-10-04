"""Patient workflow through the real Streamlit pages (AppTest)."""

import pytest
from sqlalchemy import select

from core.db import get_session
from core.models import Consent, PatientEntry, Prescription, Role
from services import clinical_service, consent_service, prescription_service, user_service
from services.clinical_service import ConsultationInput
from services.prescription_service import MedicineInput
from tests.test_phase2_fixes import AHMED_PATIENT, AYESHA, ids, markup, org_id, start


def as_ahmed(page: str):
    return start(role=Role.PATIENT, user_id=ids("Ahmed Khan"), page=page)


def click(at, label: str, index: int = 0):
    [b for b in at.button if b.label == label][index].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_patient_nav_has_documents_and_pages_render():
    at = as_ahmed("views/patient/documents.py")
    html = markup(at)
    assert "Documents" in html and "Added by me" in str([o for s in at.segmented_control for o in s.options])
    assert "Discharge summary" in html or "Lab report" in html     # seeded provider/organization documents


def test_add_health_note_from_home_shows_patient_provided():
    at = as_ahmed("views/patient/home.py")
    click(at, "Add a health note")
    assert any(t.label == "Title *" for t in at.text_input)
    at.text_input(key="pt_entry_title").set_value("UI: home BP 128/84")
    at.text_area(key="pt_entry_details").set_value("Evening readings")
    click(at, "Save")
    with get_session() as s:
        e = s.scalar(select(PatientEntry).where(PatientEntry.title == "UI: home BP 128/84"))
        assert e is not None and e.entry_type == "note"
    at.switch_page("views/patient/my_health.py")
    at.run()
    html = markup(at)
    assert "UI: home BP 128/84" in html and "Patient-provided" in html


def test_entry_validation_shown_inline():
    at = as_ahmed("views/patient/my_health.py")
    click(at, "Add a health note")
    click(at, "Save")
    assert "Please add a short title." in markup(at)


def test_patient_allergy_shown_labelled_and_doctor_sees_it():
    at = as_ahmed("views/patient/my_health.py")
    click(at, "Add allergy or information")
    assert at.selectbox(key="pt_entry_kind").value == "allergy"
    at.text_input(key="pt_entry_title").set_value("UI-Sulfa")
    click(at, "Save")
    at.run()
    assert "UI-Sulfa · Patient-provided" in markup(at)
    # Dr. Ayesha (active consent) sees it in the patient header, labelled.
    doc = start(page="views/doctor/patients.py", sel_patient=AHMED_PATIENT)
    assert "UI-Sulfa · Patient-provided" in markup(doc) and "Penicillin" in markup(doc)


def test_upload_dialog_requires_a_file():
    at = as_ahmed("views/patient/documents.py")
    click(at, "Upload a document")
    at.text_input(key="pt_upload_title").set_value("No file")
    click(at, "Upload")
    assert "The file is empty." in markup(at) or "Only PDF, PNG or JPG files are supported." in markup(at)


def test_patient_chooses_pharmacy_for_issued_prescription():
    with get_session() as s:
        ayesha = user_service.make_actor(s, AYESHA)
        c = clinical_service.save_consultation(s, ayesha, AHMED_PATIENT, ConsultationInput(complaint="UI patient send",
                                                                                         assessment="x"), finalize=True)
        rx = prescription_service.save_draft(s, ayesha, AHMED_PATIENT, [MedicineInput(
            drug_name="Cetirizine", strength="10 mg", frequency="once daily", duration_days=5, quantity=5)],
            consultation_id=c.id)
        rx_id = prescription_service.issue(s, ayesha, rx.id).id
    at = as_ahmed("views/patient/prescriptions.py")
    assert "Choose a pharmacy" in markup(at)
    at.selectbox(key=f"pharm_{rx_id}").set_value(org_id("HealthPlus Pharmacy"))
    at.button(key=f"send_{rx_id}").click()
    at.run()
    assert any("Only HealthPlus Pharmacy receives it" in c.value for c in at.caption)
    at.button(key="pt_send_ok").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    with get_session() as s:
        sent = s.get(Prescription, rx_id)
        assert sent.status == "sent" and sent.pharmacy.name == "HealthPlus Pharmacy"
    assert "Sent to HealthPlus Pharmacy. The pharmacist will check it" in markup(at)


def test_share_all_shows_warning_and_explicit_confirmation():
    at = as_ahmed("views/patient/consent.py")
    click(at, "Share Records with a Doctor")
    at.radio(key="share_mode").set_value("all").run()
    html = markup(at)
    assert "Full medical record access" in html
    assert "Confirm & Share All Records" in [b.label for b in at.button]


@pytest.fixture
def restore_ayesha_consent():
    yield
    with get_session() as s:
        ahmed = user_service.make_actor(s, ids("Ahmed Khan"))
        consent_service.grant(s, ahmed, provider_id=AYESHA, organization_id=org_id("Clifton Family Clinic"),
                              scope_type="all", confirm_all=True)


def test_revoke_dialog_removes_access(restore_ayesha_consent):
    with get_session() as s:
        cid = next(c.id for c in s.scalars(select(Consent).where(Consent.provider_id == AYESHA,
                                                                 Consent.organization_id == org_id("Clifton Family Clinic"),
                                                                 Consent.status == "active")))
    at = as_ahmed("views/patient/consent.py")
    at.button(key=f"rev_{cid}").click()
    at.run()
    at.button(key=f"rv_ok_{cid}").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    with get_session() as s:
        assert s.get(Consent, cid).status == "revoked"
    doctor = start(page="views/doctor/patients.py", sel_patient=AHMED_PATIENT)
    assert "ACCESS RESTRICTED" in markup(doctor)
