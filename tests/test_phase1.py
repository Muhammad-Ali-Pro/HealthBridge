"""Schema, seed data, multi-organization providers and configuration."""

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from core.config import load_settings
from core.db import init_db, make_engine
from core.models import (
    SCHEMA_VERSION,
    ClinicalNote,
    Consent,
    Consultation,
    Dispensing,
    Document,
    Invoice,
    LabOrder,
    LabReport,
    LabResult,
    Organization,
    OrgType,
    Patient,
    PatientEntry,
    Prescription,
    PrescriptionStatus,
    ProviderOrganization,
    SourceType,
    TimelineEvent,
    User,
)
from data.catalog import load_drug_catalog
from data.seed import seed_if_empty
from services import record_service, user_service

EXPECTED_TABLES = {
    "organizations", "users", "provider_organizations", "patients", "consents", "consent_scopes",
    "consultations", "clinical_notes", "prescriptions", "prescription_items", "dispensings", "invoices",
    "lab_orders", "lab_results", "lab_reports", "documents", "patient_entries",
    "timeline_events", "ai_flags", "ai_summaries", "audit_logs",
}


def count(session, model, *where) -> int:
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_schema_creates_all_tables(engine):
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_seed_counts(seeded):
    assert count(seeded, Organization) == 8
    assert {t: count(seeded, Organization, Organization.org_type == t) for t in OrgType} == {
        "clinic": 3, "hospital": 2, "laboratory": 1, "pharmacy": 2}
    assert count(seeded, User) == 13
    assert count(seeded, Patient) == 7
    assert count(seeded, ProviderOrganization) == 9
    assert count(seeded, Consent) == 13
    assert count(seeded, Consultation) == 12
    assert count(seeded, ClinicalNote) == 2
    assert count(seeded, Prescription) == 11
    assert count(seeded, Dispensing) == 6
    assert count(seeded, Invoice) == 6
    assert count(seeded, LabOrder) == 6
    assert count(seeded, LabResult) == 4
    assert count(seeded, LabReport) == 2
    assert count(seeded, Document) == 4
    assert count(seeded, PatientEntry) == 2


def test_seed_is_idempotent(seeded):
    assert seed_if_empty(seeded) is False
    assert count(seeded, User) == 13


def test_every_record_keeps_organization_and_source(seeded):
    for model in (Consultation, ClinicalNote, Prescription, Dispensing, Invoice, LabOrder, LabReport):
        assert count(seeded, model, model.organization_id.is_(None)) == 0, model.__name__
    # Only patient-provided entries have no organization.
    assert count(seeded, TimelineEvent, TimelineEvent.organization_id.is_(None),
                 TimelineEvent.source_type != SourceType.PATIENT) == 0
    assert count(seeded, TimelineEvent, TimelineEvent.record_category.is_(None)) == 0
    assert count(seeded, Document, Document.organization_id.is_(None), Document.source_type != SourceType.PATIENT) == 0


def test_provider_can_work_at_multiple_organizations(seeded, actor):
    arif = actor("Dr. Arif Hassan")
    assert [m.organization.name for m in user_service.memberships(seeded, arif.id)] == [
        "South City Hospital", "Clifton Medical Centre"]
    assert arif.organization.name == "South City Hospital"  # primary by default
    assert actor("Dr. Arif Hassan", "Clifton Medical Centre").organization.name == "Clifton Medical Centre"


def test_one_patient_timeline_preserves_each_source(seeded, actor):
    record = record_service.own_record(seeded, actor("Ahmed Khan"))
    assert {(c.provider_name, c.organization_name) for c in record.consultations} == {
        ("Dr. Ayesha Malik", "Clifton Family Clinic"), ("Dr. Arif Hassan", "Clifton Medical Centre"),
        ("Dr. Ayesha Malik", "City Hospital")}
    sources = {e.source for e in record.timeline}
    assert {"Patient", "Dr. Arif Hassan / Clifton Medical Centre", "HealthLab Diagnostics", "HealthPlus Pharmacy"} <= sources
    assert {d.source for d in record.documents} == {"Patient uploaded", "Uploaded by City Hospital",
                                                     "Uploaded by HealthLab Diagnostics"}
    assert [e.entry_type for e in record.patient_entries] == ["allergy", "note"]


def test_seed_covers_every_workflow_stage(seeded):
    assert {rx.status for rx in seeded.scalars(select(Prescription))} == {
        PrescriptionStatus.DRAFT, PrescriptionStatus.ISSUED, PrescriptionStatus.SENT, PrescriptionStatus.VERIFIED,
        PrescriptionStatus.DISPENSED}
    assert {o.status for o in seeded.scalars(select(LabOrder))} == {
        "ordered", "received", "resulted", "verified", "published"}
    assert {i.payment_status for i in seeded.scalars(select(Invoice))} == {"paid", "pending", "partially_paid"}


def test_every_dispensing_has_an_invoice_and_every_published_result_a_report(seeded):
    assert count(seeded, Dispensing) == count(seeded, Invoice)
    assert count(seeded, LabReport) == count(seeded, LabOrder, LabOrder.status == "published")
    assert count(seeded, LabReport, LabReport.document_id.is_(None)) == 0


def test_sqlite_foreign_keys_enforced(session):
    session.add(Consultation(patient_id=999, provider_id=999, organization_id=999, complaint="x"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_outdated_demo_schema_is_rebuilt(tmp_path):
    eng = make_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE clinics (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("PRAGMA user_version = 1"))
    assert init_db(eng) is True
    assert set(inspect(eng).get_table_names()) == EXPECTED_TABLES
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA user_version")).scalar() == SCHEMA_VERSION
    assert init_db(eng) is False  # already current
    eng.dispose()


def test_drug_catalog_loads():
    names = [d["name"] for d in load_drug_catalog()]
    assert len(names) == len(set(names)) == 30


def test_ai_provider_and_model_come_from_environment(monkeypatch):
    for var in ("GEMINI_API_KEY", "GEMINI_MODEL", "AI_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AI_ENABLED", "true")
    s = load_settings()
    assert s.ai_provider == "gemini" and s.env_ai_configured is False and s.gemini_model is None
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    s = load_settings()
    assert s.gemini_model == "gemini-3.5-flash-lite" and s.env_ai_configured is True
    assert "test-key-not-real" not in repr(s)
    monkeypatch.setenv("AI_ENABLED", "false")
    assert load_settings().env_ai_configured is False
