"""Phase 2 doctor workflow: search → consent → consultation → notes → documents → prescription → timeline/audit."""

import pytest
from sqlalchemy import select

from core.models import AuditAction, AuditLog, Consultation, Organization
from services import (
    access_service,
    audit_service,
    clinical_service,
    consent_service,
    document_service,
    patient_service,
    prescription_service,
    provider_service,
    record_service,
)
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError, ConsultationInput
from services.prescription_service import MedicineInput

GOOD = ConsultationInput(complaint="Chest discomfort on exertion", notes="Two episodes this week.",
                         observations="BP 134/86. ECG normal.", assessment="Atypical chest pain.",
                         diagnosis="Chest pain, unspecified", treatment_plan="Stress test.", follow_up="Review in 2 weeks.")
METFORMIN = MedicineInput(drug_name="Metformin", strength="500 mg", dosage="1 tablet", route="oral",
                          frequency="twice daily", duration_days=30, quantity=60, instructions="With meals.")


@pytest.fixture
def arif_with_consent(seeded, actor, pid):
    """Demo steps 4–7: Ahmed shares consultations, prescriptions, medications with Dr. Arif @ South City."""
    org = seeded.scalar(select(Organization.id).where(Organization.name == "South City Hospital"))
    consent_service.grant(seeded, actor("Ahmed Khan"), provider_id=actor("Dr. Arif Hassan").id, organization_id=org,
                          scope_type="selected", categories=["consultations", "prescriptions", "medications"])
    return actor("Dr. Arif Hassan")


def audit_events(session, patient_id):
    return [(e.action, (e.details or {}).get("event")) for e in
            session.scalars(select(AuditLog).where(AuditLog.patient_id == patient_id).order_by(AuditLog.id))]


# 1. Search -----------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["ahmed", "HB-000001", "HB-1", "+92 300 555 0101", "3005550101", "0101"])
def test_doctor_can_search_patient_by_name_id_or_phone(seeded, actor, query):
    names = [e.patient.name for e in patient_service.directory(seeded, actor("Dr. Arif Hassan"), query)]
    assert names == ["Ahmed Khan"]


# 2–5. Consent + organization context ----------------------------------------------------


def test_without_consent_doctor_cannot_read_or_write(seeded, actor, pid):
    arif = actor("Dr. Arif Hassan")
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, arif, pid("Ahmed Khan"))
    with pytest.raises(AccessDenied):
        clinical_service.save_consultation(seeded, arif, pid("Ahmed Khan"), GOOD, finalize=True)
    with pytest.raises(AccessDenied):
        prescription_service.save_draft(seeded, arif, pid("Ahmed Khan"), [METFORMIN])


def test_consent_covers_only_permitted_categories_and_one_organization(seeded, arif_with_consent, actor, pid):
    record = record_service.get_authorized_record(seeded, arif_with_consent, pid("Ahmed Khan"))
    assert record.reports == [] and record.documents == []
    assert {e.record_category for e in record.timeline} <= {"consultations", "prescriptions"}
    at_cmc = actor("Dr. Arif Hassan", "Clifton Medical Centre")
    assert not access_service.authorize(seeded, at_cmc, pid("Ahmed Khan")).allowed
    with pytest.raises(AccessDenied):
        clinical_service.save_consultation(seeded, at_cmc, pid("Ahmed Khan"), GOOD, finalize=True)


# 6–9. Consultations, notes, documents ---------------------------------------------------


def test_doctor_creates_consultation_with_organization_context_timeline_and_audit(seeded, arif_with_consent, pid):
    ahmed = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif_with_consent, ahmed, GOOD, finalize=True)
    assert c.status == "final" and c.organization_name == "South City Hospital" and c.provider_name == "Dr. Arif Hassan"
    assert c.record_category == "hospital_records"  # written at a hospital
    row = seeded.get(Consultation, c.id)
    assert (row.patient_id, row.provider_id, row.organization_id) == (ahmed, arif_with_consent.id, arif_with_consent.organization_id)

    timeline = record_service.own_record(seeded, _patient(seeded)).timeline
    assert timeline[0].event_type == "consultation" and timeline[0].source == "Dr. Arif Hassan / South City Hospital"
    assert (AuditAction.RECORD_CREATED, "consultation") in audit_events(seeded, ahmed)


def test_validation_blocks_incomplete_final_consultation(seeded, arif_with_consent, pid):
    with pytest.raises(ClinicalValidationError) as err:
        clinical_service.save_consultation(seeded, arif_with_consent, pid("Ahmed Khan"),
                                           ConsultationInput(notes="only notes"), finalize=True)
    assert set(err.value.errors) == {"complaint", "assessment"}


def test_drafts_are_private_until_finalized(seeded, arif_with_consent, actor, pid):
    ahmed = pid("Ahmed Khan")
    draft = clinical_service.save_consultation(seeded, arif_with_consent, ahmed,
                                               ConsultationInput(complaint="Palpitations"), finalize=False)
    assert draft.status == "draft"
    assert [d.id for d in clinical_service.list_drafts(seeded, arif_with_consent)] == [draft.id]
    own = record_service.own_record(seeded, _patient(seeded))
    assert draft.id not in {c.id for c in own.consultations}
    assert all("draft" not in str(e.details.get("event")) for e in audit_service.patient_history(
        seeded, _patient(seeded), ahmed, include_activity=True))
    with pytest.raises(AccessDenied):  # another doctor cannot open it
        clinical_service.get_consultation(seeded, actor("Dr. Ayesha Malik"), draft.id)

    final = clinical_service.save_consultation(
        seeded, arif_with_consent, ahmed, GOOD.model_copy(update={"complaint": "Palpitations"}),
        finalize=True, consultation_id=draft.id)
    assert final.id == draft.id and final.status == "final"
    assert clinical_service.list_drafts(seeded, arif_with_consent) == []
    with pytest.raises(ClinicalValidationError):  # finalized records are immutable
        clinical_service.save_consultation(seeded, arif_with_consent, ahmed, GOOD, finalize=False, consultation_id=final.id)


def test_doctor_adds_clinical_note(seeded, arif_with_consent, pid):
    ahmed = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif_with_consent, ahmed, GOOD, finalize=True)
    n = clinical_service.add_note(seeded, arif_with_consent, ahmed, "follow_up", "Patient to keep symptom diary.",
                                  consultation_id=c.id)
    assert n.provider_name == "Dr. Arif Hassan" and n.note_type == "follow_up"
    assert [x.id for x in clinical_service.notes_for_consultation(seeded, arif_with_consent, c.id)] == [n.id]
    assert record_service.own_record(seeded, _patient(seeded)).timeline[0].event_type == "clinical_note"
    with pytest.raises(ClinicalValidationError):
        clinical_service.add_note(seeded, arif_with_consent, ahmed, "consultation", "   ")


def test_doctor_uploads_document(seeded, arif_with_consent, pid):
    ahmed = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif_with_consent, ahmed, GOOD, finalize=True)
    doc = document_service.upload(seeded, arif_with_consent, ahmed, file_name="ecg.pdf", data=b"%PDF-1.4 demo",
                                  doc_type="medical_report", title="Resting ECG", consultation_id=c.id)
    assert doc.source == "Uploaded by South City Hospital" and doc.has_file and doc.mime_type == "application/pdf"
    data, name, mime = document_service.read_file(seeded, arif_with_consent, doc.id)
    assert data == b"%PDF-1.4 demo" and name == "ecg.pdf"
    assert [d.id for d in document_service.for_consultation(seeded, arif_with_consent, c.id)] == [doc.id]
    assert (AuditAction.RECORD_CREATED, "document_added") in audit_events(seeded, ahmed)
    with pytest.raises(ClinicalValidationError):
        document_service.upload(seeded, arif_with_consent, ahmed, file_name="virus.exe", data=b"x",
                                doc_type="other", title="Bad")


def test_documents_list_respects_consent_scope(seeded, actor, pid):
    ayesha = actor("Dr. Ayesha Malik")  # Fatima shared no documents with Dr. Ayesha
    docs = document_service.authorized_documents(seeded, ayesha)
    assert docs and all(p.name != "Fatima Raza" for p, _ in docs)


# 10–13. Prescriptions -------------------------------------------------------------------


def test_prescription_with_multiple_medicines_draft_then_issue(seeded, arif_with_consent, pid):
    ahmed = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif_with_consent, ahmed, GOOD, finalize=True)
    second = MedicineInput(drug_name="Atorvastatin", strength="20 mg", dosage="1 tablet", frequency="once daily at night",
                           duration_days=30, quantity=30)
    rx = prescription_service.save_draft(seeded, arif_with_consent, ahmed, [METFORMIN, second], consultation_id=c.id,
                                         notes="Review renal function.")
    assert rx.status == "draft" and [i.drug_name for i in rx.items] == ["Metformin", "Atorvastatin"]
    assert rx.organization_name == "South City Hospital"
    assert rx.id not in {p.id for p in record_service.own_record(seeded, _patient(seeded)).prescriptions}

    issued = prescription_service.issue(seeded, arif_with_consent, rx.id)
    assert issued.status == "issued" and issued.issued_at is not None
    own = record_service.own_record(seeded, _patient(seeded))
    assert own.timeline[0].event_type == "prescription_issued" and "Metformin 500 mg" in own.timeline[0].summary
    assert (AuditAction.RECORD_CREATED, "prescription_issued") in audit_events(seeded, ahmed)
    with pytest.raises(ClinicalValidationError):  # issued prescriptions cannot be edited
        prescription_service.save_draft(seeded, arif_with_consent, ahmed, [METFORMIN], prescription_id=rx.id)


def test_prescription_validation_and_allergy_warning(seeded, arif_with_consent, pid):
    ahmed = pid("Ahmed Khan")
    errors = prescription_service.validate_items([MedicineInput(drug_name="Metformin")])
    assert {"0.strength", "0.frequency", "0.duration_days", "0.quantity"} <= set(errors)
    allergies = prescription_service.patient_allergies(seeded, arif_with_consent, ahmed)
    warnings = prescription_service.allergy_warnings(allergies, [MedicineInput(drug_name="Amoxicillin")])
    assert warnings and "penicillin" in warnings[0].lower()
    bad = prescription_service.save_draft(seeded, arif_with_consent, ahmed, [MedicineInput(drug_name="Metformin")])
    with pytest.raises(ClinicalValidationError):
        prescription_service.issue(seeded, arif_with_consent, bad.id)


def test_doctor_lists_drafts_and_follow_ups(seeded, actor):
    arif = actor("Dr. Arif Hassan")
    rxs = provider_service.my_prescriptions(seeded, arif, include_drafts=True)
    assert [rx.status for rx in rxs if rx.status == "draft"] == ["draft"]
    assert [c.patient_name for c in provider_service.pending_follow_ups(seeded, arif)] == ["Bilal Chaudhry", "Fatima Raza"]


def _patient(seeded):
    from core.models import User
    from services import user_service
    return user_service.make_actor(seeded, seeded.scalar(select(User.id).where(User.name == "Ahmed Khan")))
