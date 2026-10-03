"""Access control is enforced in the service layer: identity + organization + consent + scope + lifecycle."""

import pytest
from sqlalchemy import func, select

from core.models import AuditAction, AuditLog, ConsentStatus, RecordCategory
from services import (
    access_service,
    consent_service,
    lab_service,
    patient_service,
    pharmacy_service,
    record_service,
)
from services.access_service import AccessDenied


def audits(session, action, **where):
    stmt = select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    for k, v in where.items():
        stmt = stmt.where(getattr(AuditLog, k) == v)
    return session.scalar(stmt)


def test_patient_sees_own_full_record_only(seeded, actor, pid):
    me = actor("Ahmed Khan")
    assert access_service.authorize(seeded, me, pid("Ahmed Khan")).via == "self"
    assert not access_service.authorize(seeded, me, pid("Fatima Raza")).allowed
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, me, pid("Fatima Raza"))


def test_demo_starts_with_dr_arif_locked_out_of_ahmeds_record(seeded, actor, pid):
    for org in ("South City Hospital", "Clifton Medical Centre"):
        decision = access_service.authorize(seeded, actor("Dr. Arif Hassan", org), pid("Ahmed Khan"))
        assert not decision.allowed
        assert decision.reason == "Patient consent is required to access this patient's HealthBridge records."


def test_doctor_with_all_records_consent(seeded, actor, pid):
    record = record_service.get_authorized_record(seeded, actor("Dr. Ayesha Malik"), pid("Ahmed Khan"))
    assert record.access.scope_type == "all"
    assert len(record.consultations) == 4 and len(record.reports) == 2 and len(record.notes) == 2
    assert len(record.documents) == 3 and len(record.patient_entries) == 2
    assert record.patient.conditions == ["Type 2 diabetes"]


def test_billing_is_never_shared_even_with_all_records(seeded, actor, pid):
    record = record_service.get_authorized_record(seeded, actor("Dr. Ayesha Malik"), pid("Ahmed Khan"))
    assert all(rx.invoice is None for rx in record.prescriptions)
    assert all(e.record_category != "billing" for e in record.timeline)
    own = record_service.own_record(seeded, actor("Ahmed Khan"))
    assert own.prescriptions[-1].invoice.payment_status == "paid"
    assert any(e.event_type == "invoice_issued" for e in own.timeline)


def test_consent_is_organization_specific(seeded, actor, pid):
    """Same doctor, other organization: the one-consultation consent there has expired → no access."""
    at_hospital = actor("Dr. Ayesha Malik", "City Hospital")
    assert not access_service.authorize(seeded, at_hospital, pid("Ahmed Khan")).allowed
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, at_hospital, pid("Ahmed Khan"))
    assert audits(seeded, AuditAction.ACCESS_DENIED, actor_id=at_hospital.id) == 1


def test_consent_is_provider_specific(seeded, actor, pid):
    assert not access_service.authorize(seeded, actor("Dr. Imran Qureshi", "City Hospital"), pid("Ahmed Khan")).allowed
    assert not access_service.authorize(seeded, actor("Dr. Imran Qureshi"), pid("Ahmed Khan")).allowed  # revoked


def test_selected_scope_filters_every_record_type(seeded, actor, pid):
    """Fatima shared consultations + prescriptions + medications with Dr. Ayesha at Clifton Family Clinic."""
    record = record_service.get_authorized_record(seeded, actor("Dr. Ayesha Malik"), pid("Fatima Raza"))
    assert [c.organization_name for c in record.consultations] == ["Gulshan Medical Centre"]  # hospital visit hidden
    assert record.reports == [] and record.documents == [] and record.patient_entries == []
    assert {e.record_category for e in record.timeline} == {"consultations", "prescriptions"}
    assert {m.drug_name for m in record.medications} == {"Amlodipine", "Bisoprolol"}


def test_conditions_hidden_without_consultation_scope(seeded, actor, pid):
    record = record_service.get_authorized_record(seeded, actor("Dr. Ayesha Malik"), pid("Bilal Chaudhry"))
    assert record.patient.conditions is None
    assert record.patient.allergies == ["NSAIDs"]  # safety-critical, shown with any consent
    assert record.consultations == [] and [o.test_name for o in record.reports] == ["Lipid panel"]


def test_out_of_scope_category_is_denied_and_audited(seeded, actor, pid):
    ayesha = actor("Dr. Ayesha Malik")
    with pytest.raises(AccessDenied):
        access_service.require(seeded, ayesha, pid("Fatima Raza"), RecordCategory.LAB_REPORTS)
    assert audits(seeded, AuditAction.ACCESS_DENIED, actor_id=ayesha.id, patient_id=pid("Fatima Raza")) == 1


def test_record_access_is_audited_once_per_session(seeded, actor, pid):
    ayesha = actor("Dr. Ayesha Malik")
    before = audits(seeded, AuditAction.RECORD_ACCESSED, actor_id=ayesha.id)
    record_service.get_authorized_record(seeded, ayesha, pid("Fatima Raza"), view="patient_record")
    record_service.get_authorized_record(seeded, ayesha, pid("Fatima Raza"), view="patient_record")  # rerun
    assert audits(seeded, AuditAction.RECORD_ACCESSED, actor_id=ayesha.id) == before + 1
    entry = seeded.scalars(select(AuditLog).where(AuditLog.actor_id == ayesha.id, AuditLog.patient_id == pid("Fatima Raza"),
                                                  AuditLog.action == AuditAction.RECORD_ACCESSED)).one()
    assert entry.organization_id == ayesha.organization_id
    assert sorted(entry.details["scope"]) == ["consultations", "medications", "prescriptions"]


def test_patient_self_access_is_not_logged_as_provider_access(seeded, actor):
    before = audits(seeded, AuditAction.RECORD_ACCESSED)
    record_service.own_record(seeded, actor("Ahmed Khan"))
    assert audits(seeded, AuditAction.RECORD_ACCESSED) == before


def test_directory_reveals_identity_only(seeded, actor):
    entries = patient_service.directory(seeded, actor("Dr. Arif Hassan"))
    assert len(entries) == 7
    assert not hasattr(entries[0].patient, "allergies")
    assert [e.patient.name for e in entries if e.access.allowed] == ["Bilal Chaudhry", "Fatima Raza"]


def test_pharmacy_sees_only_routed_prescriptions_minimum_necessary(seeded, actor, pid):
    sana = actor("Sana Iqbal")
    rxs = pharmacy_service.list_prescriptions(seeded, sana)
    assert rxs and all(rx.pharmacy_name == "HealthPlus Pharmacy" for rx in rxs)
    assert all(rx.reason is None for rx in rxs)  # no consultation reason / diagnosis
    assert all(rx.status != "issued" for rx in rxs)  # not-yet-sent prescriptions are invisible
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, sana, pid("Ahmed Khan"))
    assert pharmacy_service.queue_overview(seeded, sana) == {
        "pending": 2, "awaiting_verification": 1, "ready_to_dispense": 1, "dispensed_today": 1, "dispensed_total": 4}
    invoices = pharmacy_service.list_invoices(seeded, sana)
    assert len(invoices) == 4 and all(i.pharmacy_name == "HealthPlus Pharmacy" for i in invoices)
    assert pharmacy_service.billing_overview(seeded, sana)["outstanding"] == 120.0


def test_lab_sees_only_its_orders(seeded, actor, pid):
    nadia = actor("Nadia Farooq")
    orders = lab_service.list_orders(seeded, nadia)
    assert len(orders) == 6 and all(o.lab_name == "HealthLab Diagnostics" for o in orders)
    assert lab_service.overview(seeded, nadia)["awaiting_verification"] == 1
    assert {o.report_number is not None for o in orders if o.status == "published"} == {True}
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, nadia, pid("Ahmed Khan"))
    with pytest.raises(AccessDenied):
        pharmacy_service.list_prescriptions(seeded, nadia)


def test_unpublished_lab_results_hidden_from_patient(seeded, actor):
    record = record_service.own_record(seeded, actor("Ahmed Khan"))
    pending = next(o for o in record.reports if o.status == "received")
    published = next(o for o in record.reports if o.status == "published")
    assert pending.values == [] and published.values and published.report_number


def test_expired_and_revoked_consents_report_their_status(seeded, actor):
    statuses = {(c.provider_name, c.organization_name): c.status
                for c in consent_service.list_for_patient(seeded, actor("Ahmed Khan"))}
    assert statuses == {
        ("Dr. Ayesha Malik", "Clifton Family Clinic"): ConsentStatus.ACTIVE,
        ("Dr. Ayesha Malik", "City Hospital"): ConsentStatus.EXPIRED,
        ("Dr. Arif Hassan", "Clifton Medical Centre"): ConsentStatus.EXPIRED,
        ("Dr. Imran Qureshi", "Gulshan Medical Centre"): ConsentStatus.REVOKED,
    }
