"""Patient workflow (docs/workflows/patient) + shared architecture A1–A3 — service, authorization and audit tests."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, inspect, select, text

from core.models import (
    SCHEMA_VERSION,
    AuditLog,
    Consent,
    Document,
    EventType,
    Organization,
    Patient,
    Prescription,
    TimelineEvent,
    utcnow,
)
from services import (
    clinical_service,
    consent_service,
    copilot_service,
    document_service,
    lab_service,
    patient_entry_service,
    pharmacy_service,
    prescription_service,
    record_service,
)
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError, ConsultationInput
from services.prescription_service import MedicineInput

PDF = b"%PDF-1.4 demo"


def org(seeded, name):
    return seeded.scalar(select(Organization.id).where(Organization.name == name))


@pytest.fixture
def ahmed(actor):
    return actor("Ahmed Khan")


@pytest.fixture
def arif(seeded, actor):
    """Demo consent: Ahmed → Dr. Arif @ South City Hospital, consultations + prescriptions + medications."""
    consent_service.grant(seeded, actor("Ahmed Khan"), provider_id=actor("Dr. Arif Hassan").id,
                          organization_id=org(seeded, "South City Hospital"), scope_type="selected",
                          categories=["consultations", "prescriptions", "medications"])
    return actor("Dr. Arif Hassan")


def arif_consent_id(seeded, ahmed):
    return next(c.id for c in consent_service.list_for_patient(seeded, ahmed)
                if c.provider_name == "Dr. Arif Hassan" and c.organization_name == "South City Hospital" and c.active)


def audit_for(seeded, resource_type, resource_id):
    return seeded.scalars(select(AuditLog).where(AuditLog.resource_type == resource_type,
                                                 AuditLog.resource_id == resource_id)).all()


def issued_for_ahmed(seeded, actor, pid, drug="Metformin"):
    ayesha = actor("Dr. Ayesha Malik")
    c = clinical_service.save_consultation(seeded, ayesha, pid("Ahmed Khan"),
                                           ConsultationInput(complaint="Review", assessment="Stable"), finalize=True)
    rx = prescription_service.save_draft(seeded, ayesha, pid("Ahmed Khan"), [MedicineInput(
        drug_name=drug, strength="500 mg", dosage="1 tablet", frequency="twice daily", duration_days=30, quantity=60)],
        consultation_id=c.id)
    return prescription_service.issue(seeded, ayesha, rx.id)


# --- A1 / A2 / A3: shared architecture --------------------------------------------------------------


def test_activity_source_follows_the_actor(seeded, ahmed, actor, pid):
    entry = patient_entry_service.add_entry(seeded, ahmed, "note", "Home BP 130/85")
    ev = seeded.scalars(select(TimelineEvent).where(TimelineEvent.ref_table == "patient_entries",
                                                    TimelineEvent.ref_id == entry.id)).one()
    assert (ev.source_type, ev.organization_id, ev.actor_id) == ("patient", None, ahmed.id)
    [log] = audit_for(seeded, "patient_entries", entry.id)
    assert (log.actor_type, log.provider_id, log.organization_id) == ("patient", None, None)
    assert log.details["source"] == "patient" and log.details["entry_type"] == "note"

    ayesha = actor("Dr. Ayesha Malik")      # doctors are unchanged: provider source, provider_id = doctor
    c = clinical_service.save_consultation(seeded, ayesha, pid("Ahmed Khan"), ConsultationInput(complaint="x", assessment="y"),
                                           finalize=True)
    ev = seeded.scalars(select(TimelineEvent).where(TimelineEvent.ref_table == "consultations", TimelineEvent.ref_id == c.id)).one()
    [log] = [a for a in audit_for(seeded, "consultations", c.id)]
    assert ev.source_type == "provider" and log.provider_id == ayesha.id and log.details["source"] == "provider"


def test_new_event_types_and_verification_columns(seeded):
    assert EventType.PAYMENT_RECORDED == "payment_recorded" and EventType.INVOICE_CANCELLED == "invoice_cancelled"
    assert SCHEMA_VERSION == 7
    cols = {c["name"] for c in inspect(seeded.get_bind()).get_columns("prescriptions")}
    assert {"verified_at", "verified_by"} <= cols
    verified = seeded.scalars(select(Prescription).where(Prescription.status.in_(["verified", "dispensed"]))).all()
    assert verified and all(rx.verified_at and rx.verifier.role == "pharmacist" for rx in verified)


def test_outdated_demo_database_is_rebuilt(tmp_path):
    from core.db import init_db

    eng = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE prescriptions (id INTEGER PRIMARY KEY)"))
        conn.execute(text("PRAGMA user_version = 6"))
    init_db(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("prescriptions")}
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA user_version")).scalar() == SCHEMA_VERSION
    assert "verified_by" in cols
    eng.dispose()


# --- Patient-provided entries (D2, D15) ----------------------------------------------------------------


def test_patient_adds_note_and_allergy_without_touching_clinical_allergies(seeded, ahmed, pid):
    before = list(seeded.get(Patient, pid("Ahmed Khan")).allergies)
    patient_entry_service.add_entry(seeded, ahmed, "note", "Home BP 130/85", "Most mornings")
    patient_entry_service.add_entry(seeded, ahmed, "allergy", "Ibuprofen", "Rash")
    assert seeded.get(Patient, pid("Ahmed Khan")).allergies == before == ["Penicillin"]
    own = record_service.own_record(seeded, ahmed)
    assert {"Home BP 130/85", "Ibuprofen"} <= {e.title for e in own.patient_entries}
    assert own.patient.reported_allergies == ["Shellfish (self-reported)", "Ibuprofen"]
    mine = [e for e in own.timeline if e.event_type == "patient_entry"]
    assert mine and all(e.source_type == "patient" for e in mine)
    assert any(e.summary == "Allergy reported: Ibuprofen" for e in mine)


def test_entry_validation_and_append_only(seeded, ahmed):
    with pytest.raises(ClinicalValidationError) as exc:
        patient_entry_service.add_entry(seeded, ahmed, "note", "  ")
    assert "title" in exc.value.errors
    with pytest.raises(ClinicalValidationError):
        patient_entry_service.add_entry(seeded, ahmed, "diagnosis", "x")
    with pytest.raises(ClinicalValidationError):
        patient_entry_service.add_entry(seeded, ahmed, "note", "x" * 201)
    assert not hasattr(patient_entry_service, "update_entry") and not hasattr(patient_entry_service, "delete_entry")


def test_only_the_patient_can_add_entries(seeded, actor):
    for who in (actor("Dr. Ayesha Malik"), actor("Sana Iqbal"), actor("Nadia Farooq")):
        with pytest.raises(AccessDenied):
            patient_entry_service.add_entry(seeded, who, "note", "x")


# --- D1: patient-reported allergies reach consented doctors ---------------------------------------------


def test_reported_allergies_visible_with_any_active_consent_and_labelled(seeded, arif, ahmed, actor, pid):
    patient_entry_service.add_entry(seeded, ahmed, "allergy", "Ibuprofen")
    record = record_service.get_authorized_record(seeded, arif, pid("Ahmed Khan"))
    assert record.patient.reported_allergies == ["Shellfish (self-reported)", "Ibuprofen"]
    assert record.patient.allergies == ["Penicillin"]                  # kept separate
    assert record.patient_entries == []                                # other entries still need "documents"
    assert prescription_service.reported_allergies(seeded, arif, pid("Ahmed Khan")) == ["Shellfish (self-reported)", "Ibuprofen"]

    consent_service.revoke(seeded, ahmed, arif_consent_id(seeded, ahmed))
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, arif, pid("Ahmed Khan"))
    with pytest.raises(AccessDenied):
        prescription_service.reported_allergies(seeded, arif, pid("Ahmed Khan"))
    with pytest.raises(AccessDenied):               # same doctor, other organization
        record_service.get_authorized_record(seeded, actor("Dr. Arif Hassan", "Clifton Medical Centre"), pid("Ahmed Khan"))


def test_reported_allergy_triggers_prescribing_warning():
    warnings = prescription_service.allergy_warnings(["Ibuprofen (patient-reported)"], [MedicineInput(drug_name="Ibuprofen")])
    assert warnings and "patient-reported" in warnings[0]


def test_expired_consent_hides_reported_allergies(seeded, ahmed, actor, pid):
    c = consent_service.grant(seeded, ahmed, provider_id=actor("Dr. Arif Hassan").id,
                              organization_id=org(seeded, "South City Hospital"), scope_type="selected",
                              categories=["prescriptions"], duration="hours_24")
    seeded.get(Consent, c.id).expires_at = utcnow() - timedelta(minutes=1)
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, actor("Dr. Arif Hassan"), pid("Ahmed Khan"))


# --- Patient document upload (D3) ----------------------------------------------------------------------


def test_patient_upload_is_patient_provided_and_audited(seeded, ahmed, arif, actor, pid):
    doc = document_service.upload_own(seeded, ahmed, file_name="bp.pdf", data=PDF, doc_type="medical_report",
                                      title="BP diary")
    row = seeded.get(Document, doc.id)
    assert (row.source_type, row.organization_id, row.uploaded_by) == ("patient", None, ahmed.id)
    assert document_service.read_file(seeded, ahmed, doc.id)[0] == PDF
    [log] = audit_for(seeded, "documents", doc.id)
    assert (log.actor_type, log.provider_id, log.details["event"]) == ("patient", None, "document_added")
    assert "storage" not in str(log.details) and str(row.storage_path) not in str(log.details)
    assert any(e.ref_id == doc.id and e.source_type == "patient" for e in record_service.own_record(seeded, ahmed).timeline
               if e.event_type == "document_added")
    # Documents are not shared with Dr. Arif → he cannot open it; another patient cannot either.
    with pytest.raises(AccessDenied):
        document_service.read_file(seeded, arif, doc.id)
    with pytest.raises(AccessDenied):
        document_service.read_file(seeded, actor("Fatima Raza"), doc.id)
    assert document_service.read_file(seeded, actor("Dr. Ayesha Malik"), doc.id)[0] == PDF   # all-records consent


@pytest.mark.parametrize("name, data, title, field", [
    ("run.exe", PDF, "x", "file"), ("a.pdf", b"", "x", "file"), ("a.pdf", "TOO_BIG", "x", "file"),
    ("a.pdf", PDF, "  ", "title"),
], ids=["type", "empty", "too-big", "no-title"])
def test_patient_upload_validation(seeded, ahmed, name, data, title, field):
    data = b"x" * (10 * 1024 * 1024 + 1) if data == "TOO_BIG" else data
    with pytest.raises(ClinicalValidationError) as exc:
        document_service.upload_own(seeded, ahmed, file_name=name, data=data, doc_type="other", title=title)
    assert field in exc.value.errors
    assert not seeded.scalars(select(Document).where(Document.title == title.strip(), Document.source_type == "patient")).all() \
        or title.strip() == ""


def test_only_patients_use_patient_upload(seeded, actor):
    with pytest.raises(AccessDenied):
        document_service.upload_own(seeded, actor("Dr. Ayesha Malik"), file_name="a.pdf", data=PDF, doc_type="other", title="x")


def test_uploading_doctor_loses_document_access_after_revocation(seeded, ahmed, actor, pid):
    ayesha = actor("Dr. Ayesha Malik")
    doc = document_service.upload(seeded, ayesha, pid("Ahmed Khan"), file_name="ecg.pdf", data=PDF,
                                  doc_type="medical_report", title="ECG")
    assert document_service.read_file(seeded, ayesha, doc.id)[0] == PDF
    consent_id = next(c.id for c in consent_service.list_for_patient(seeded, ahmed)
                      if c.provider_name == "Dr. Ayesha Malik" and c.status == "active")
    consent_service.revoke(seeded, ahmed, consent_id)
    with pytest.raises(AccessDenied):
        document_service.read_file(seeded, ayesha, doc.id)


# --- D5: patient chooses the pharmacy ----------------------------------------------------------------------


def test_patient_sends_issued_prescription_to_chosen_pharmacy(seeded, ahmed, actor, pid):
    rx = issued_for_ahmed(seeded, actor, pid)
    healthplus = org(seeded, "HealthPlus Pharmacy")
    sent = prescription_service.send_to_pharmacy(seeded, ahmed, rx.id, healthplus)
    assert sent.status == "sent" and sent.pharmacy_name == "HealthPlus Pharmacy"
    assert rx.id in [r.id for r in pharmacy_service.list_prescriptions(seeded, actor("Sana Iqbal"))]
    log = [a for a in audit_for(seeded, "prescriptions", rx.id) if a.details.get("event") == "prescription_sent"][-1]
    assert (log.actor_type, log.provider_id, log.organization_id) == ("patient", None, healthplus)
    ev = seeded.scalars(select(TimelineEvent).where(TimelineEvent.ref_id == rx.id,
                                                    TimelineEvent.event_type == "prescription_sent")).one()
    assert ev.source_type == "patient" and "by you" in ev.summary


def test_patient_send_guards(seeded, ahmed, actor, pid):
    rx = issued_for_ahmed(seeded, actor, pid)
    with pytest.raises(ClinicalValidationError):            # not a pharmacy
        prescription_service.send_to_pharmacy(seeded, ahmed, rx.id, org(seeded, "South City Hospital"))
    prescription_service.send_to_pharmacy(seeded, ahmed, rx.id, org(seeded, "HealthPlus Pharmacy"))
    with pytest.raises(ClinicalValidationError):            # no longer issued
        prescription_service.send_to_pharmacy(seeded, ahmed, rx.id, org(seeded, "CarePoint Pharmacy"))
    with pytest.raises(AccessDenied):                       # someone else's prescription
        prescription_service.send_to_pharmacy(seeded, actor("Fatima Raza"), rx.id, org(seeded, "HealthPlus Pharmacy"))


def test_doctor_send_branch_unchanged(seeded, actor, pid):
    rx = issued_for_ahmed(seeded, actor, pid)
    with pytest.raises(AccessDenied):                       # a different doctor still cannot send it
        prescription_service.send_to_pharmacy(seeded, actor("Dr. Arif Hassan"), rx.id, org(seeded, "HealthPlus Pharmacy"))
    sent = prescription_service.send_to_pharmacy(seeded, actor("Dr. Ayesha Malik"), rx.id, org(seeded, "HealthPlus Pharmacy"))
    assert sent.status == "sent"


# --- Patient cannot modify clinician / pharmacy / lab / AI data -------------------------------------------


def test_patient_cannot_modify_clinical_prescription_lab_or_ai_data(seeded, ahmed, actor, pid):
    me = pid("Ahmed Khan")
    with pytest.raises(AccessDenied):
        clinical_service.save_consultation(seeded, ahmed, me, ConsultationInput(complaint="x", assessment="y"), finalize=True)
    with pytest.raises(AccessDenied):
        clinical_service.add_note(seeded, ahmed, me, "consultation", "x")
    with pytest.raises(AccessDenied):
        prescription_service.save_draft(seeded, ahmed, me, [MedicineInput(drug_name="X", strength="1", frequency="d",
                                                                         duration_days=1, quantity=1)])
    with pytest.raises(AccessDenied):
        lab_service.list_orders(seeded, ahmed)
    with pytest.raises(AccessDenied):
        copilot_service.generate(seeded, ahmed, me)
    with pytest.raises(AccessDenied):
        pharmacy_service.list_prescriptions(seeded, ahmed)


def test_revocation_blocks_every_ai_entry_point(seeded, arif, ahmed, pid):
    me = pid("Ahmed Khan")
    result = copilot_service.generate(seeded, arif, me)
    consent_service.revoke(seeded, ahmed, arif_consent_id(seeded, ahmed))
    for call in (lambda: copilot_service.preview(seeded, arif, me), lambda: copilot_service.generate(seeded, arif, me),
                 lambda: copilot_service.latest(seeded, arif, me),
                 lambda: copilot_service.flags_for_summary(seeded, arif, result.summary_id) or
                 copilot_service.resolve_sources(seeded, arif, me, ["PROFILE"])):
        with pytest.raises(AccessDenied):
            call()


def test_patient_history_lists_own_activity_and_billing_stays_private(seeded, ahmed, arif, pid):
    patient_entry_service.add_entry(seeded, ahmed, "allergy", "Ibuprofen")
    from services import audit_service

    history = audit_service.patient_history(seeded, ahmed, pid("Ahmed Khan"), include_activity=True)
    assert any(e.actor_type == "patient" and e.details.get("event") == "patient_entry" for e in history)
    with pytest.raises(AccessDenied):
        audit_service.patient_history(seeded, arif, pid("Ahmed Khan"))
    doctor_view = record_service.get_authorized_record(seeded, arif, pid("Ahmed Khan"))
    assert all(rx.invoice is None and rx.invoices == [] for rx in doctor_view.prescriptions)
    assert all(e.record_category != "billing" for e in doctor_view.timeline)
    own = record_service.own_record(seeded, ahmed)
    assert any(rx.invoices for rx in own.prescriptions)                 # the patient sees their own billing
