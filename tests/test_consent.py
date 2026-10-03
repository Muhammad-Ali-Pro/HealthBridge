"""Patient-controlled consent lifecycle: grant (selected / all), supersede, revoke, expire, audit."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from core.models import AuditAction, AuditLog, Consent, ConsentDuration, Consultation, utcnow
from services import access_service, audit_service, care_network_service, consent_service, record_service
from services.access_service import AccessDenied
from services.consent_service import ConsentError


def org_id(seeded, name):
    from core.models import Organization
    return seeded.scalar(select(Organization.id).where(Organization.name == name))


def grant(seeded, patient, provider, org, **kw):
    kw.setdefault("scope_type", "selected")
    return consent_service.grant(seeded, patient, provider_id=provider.id, organization_id=org_id(seeded, org), **kw)


def test_grant_selected_records_gives_scoped_access_and_is_audited(seeded, actor, pid):
    ahmed, imran = actor("Ahmed Khan"), actor("Dr. Imran Qureshi", "City Hospital")
    c = grant(seeded, ahmed, imran, "City Hospital", categories=["lab_reports"], purpose="Diabetes clinic")
    assert c.status == "active" and c.categories == ["lab_reports"] and c.display_id.startswith("CON-")

    record = record_service.get_authorized_record(seeded, imran, pid("Ahmed Khan"))
    assert record.consultations == [] and record.prescriptions == [] and len(record.reports) == 2

    entry = seeded.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CONSENT_GRANTED,
                                                  AuditLog.resource_id == c.id)).one()
    assert entry.patient_id == pid("Ahmed Khan") and entry.provider_id == imran.id
    assert entry.organization_id == imran.organization_id and entry.actor_type == "patient"
    assert entry.details["categories"] == ["lab_reports"] and entry.details["all_records"] is False
    assert entry.details["consent_id"] == c.display_id


def test_share_all_requires_explicit_confirmation(seeded, actor, pid):
    ahmed, imran = actor("Ahmed Khan"), actor("Dr. Imran Qureshi", "City Hospital")
    with pytest.raises(ConsentError):
        grant(seeded, ahmed, imran, "City Hospital", scope_type="all")
    c = grant(seeded, ahmed, imran, "City Hospital", scope_type="all", confirm_all=True)
    assert c.scope_type == "all"
    assert access_service.authorize(seeded, imran, pid("Ahmed Khan")).scope_type == "all"
    entry = seeded.scalars(select(AuditLog).where(AuditLog.resource_id == c.id,
                                                  AuditLog.action == AuditAction.CONSENT_GRANTED)).one()
    assert entry.details["all_records"] is True


def test_grant_validation(seeded, actor):
    ahmed = actor("Ahmed Khan")
    with pytest.raises(ConsentError):  # nothing selected
        grant(seeded, ahmed, actor("Dr. Imran Qureshi"), "Gulshan Medical Centre", categories=[])
    with pytest.raises(ConsentError):  # Dr. Arif does not work at Clifton Family Clinic
        grant(seeded, ahmed, actor("Dr. Arif Hassan"), "Clifton Family Clinic", categories=["prescriptions"])
    with pytest.raises(AccessDenied):  # only patients grant consent
        grant(seeded, actor("Dr. Ayesha Malik"), actor("Dr. Arif Hassan"), "South City Hospital", categories=["prescriptions"])


def test_demo_story_ahmed_shares_selected_records_with_dr_arif(seeded, actor, pid):
    """Steps 4–7: Ahmed grants Dr. Arif @ South City consultations + prescriptions + medications."""
    ahmed, arif = actor("Ahmed Khan"), actor("Dr. Arif Hassan")
    c = grant(seeded, ahmed, arif, "South City Hospital", categories=["consultations", "prescriptions", "medications"])
    record = record_service.get_authorized_record(seeded, arif, pid("Ahmed Khan"), view="medical_timeline")
    assert {x.organization_name for x in record.consultations} == {"Clifton Family Clinic", "Clifton Medical Centre"}
    assert record.reports == [] and record.documents == [] and record.patient_entries == []
    assert all(rx.invoice is None for rx in record.prescriptions)
    assert record.patient.conditions == ["Type 2 diabetes"]
    # Still locked when Dr. Arif works at his other organization.
    assert not access_service.authorize(seeded, actor("Dr. Arif Hassan", "Clifton Medical Centre"), pid("Ahmed Khan")).allowed
    history = audit_service.patient_history(seeded, ahmed, pid("Ahmed Khan"))
    assert history[0].action == "RECORD_ACCESSED" and history[0].provider_name == "Dr. Arif Hassan"
    assert any(e.action == "CONSENT_GRANTED" and e.resource_id == c.id for e in history)


def test_new_grant_supersedes_previous_consent(seeded, actor, pid):
    ahmed, ayesha = actor("Ahmed Khan"), actor("Dr. Ayesha Malik")
    old_id = access_service.authorize(seeded, ayesha, pid("Ahmed Khan")).consent_id
    new = grant(seeded, ahmed, ayesha, "Clifton Family Clinic", categories=["lab_reports"])
    assert seeded.get(Consent, old_id).status == "revoked"
    assert access_service.authorize(seeded, ayesha, pid("Ahmed Khan")).categories == ["lab_reports"]
    assert new.id != old_id


def test_revoke_removes_access_but_never_deletes_records(seeded, actor, pid):
    ahmed, ayesha = actor("Ahmed Khan"), actor("Dr. Ayesha Malik")
    consent_id = access_service.authorize(seeded, ayesha, pid("Ahmed Khan")).consent_id
    consultations_before = seeded.scalar(select(func.count()).select_from(Consultation))

    out = consent_service.revoke(seeded, ahmed, consent_id)
    assert out.status == "revoked" and out.revoked_at is not None
    assert not access_service.authorize(seeded, ayesha, pid("Ahmed Khan")).allowed
    with pytest.raises(AccessDenied):
        record_service.get_authorized_record(seeded, ayesha, pid("Ahmed Khan"))
    assert seeded.scalar(select(func.count()).select_from(Consultation)) == consultations_before
    assert seeded.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CONSENT_REVOKED,
                                                 AuditLog.resource_id == consent_id)).one().provider_id == ayesha.id


def test_patient_cannot_revoke_someone_elses_consent(seeded, actor, pid):
    fatima_consent = seeded.scalar(select(Consent.id).where(Consent.patient_id == pid("Fatima Raza")).limit(1))
    with pytest.raises(AccessDenied):
        consent_service.revoke(seeded, actor("Ahmed Khan"), fatima_consent)


def test_time_limited_consent_expires(seeded, actor, pid):
    ahmed, imran = actor("Ahmed Khan"), actor("Dr. Imran Qureshi", "City Hospital")
    c = grant(seeded, ahmed, imran, "City Hospital", categories=["prescriptions"], duration=ConsentDuration.HOURS_24)
    assert c.expires_at is not None and access_service.authorize(seeded, imran, pid("Ahmed Khan")).allowed
    seeded.get(Consent, c.id).expires_at = utcnow() - timedelta(minutes=1)
    assert not access_service.authorize(seeded, imran, pid("Ahmed Khan")).allowed


def test_one_consultation_consent_expires_after_the_visit(seeded, actor, pid):
    ahmed, imran = actor("Ahmed Khan"), actor("Dr. Imran Qureshi", "City Hospital")
    c = grant(seeded, ahmed, imran, "City Hospital", categories=["consultations"], duration=ConsentDuration.ONE_CONSULTATION)
    assert access_service.authorize(seeded, imran, pid("Ahmed Khan")).allowed
    row = seeded.get(Consent, c.id)
    row.granted_at = utcnow() - timedelta(hours=5)
    seeded.add(Consultation(patient_id=pid("Ahmed Khan"), provider_id=imran.id, organization_id=imran.organization_id,
                            date=utcnow() - timedelta(hours=4), complaint="Visit"))
    seeded.flush()
    assert not access_service.authorize(seeded, imran, pid("Ahmed Khan")).allowed


def test_patient_access_history(seeded, actor, pid):
    ahmed = actor("Ahmed Khan")
    history = audit_service.patient_history(seeded, ahmed, pid("Ahmed Khan"))
    actions = {e.action for e in history}
    assert {"CONSENT_GRANTED", "CONSENT_REVOKED", "RECORD_ACCESSED"} <= actions
    arif_access = next(e for e in history if e.action == "RECORD_ACCESSED" and e.provider_name == "Dr. Arif Hassan")
    assert arif_access.organization_name == "Clifton Medical Centre"
    activity = audit_service.patient_history(seeded, ahmed, pid("Ahmed Khan"), include_activity=True)
    events = {e.details.get("event") for e in activity if e.action == "RECORD_CREATED"}
    assert {"consultation", "prescription_issued", "dispensing", "invoice_issued", "lab_report_published",
            "document_added", "patient_entry"} <= events
    with pytest.raises(AccessDenied):  # only the patient sees their access history
        audit_service.patient_history(seeded, actor("Dr. Ayesha Malik"), pid("Ahmed Khan"))


def test_care_network(seeded, actor):
    net = care_network_service.network(seeded, actor("Ahmed Khan"))
    doctors = {d.name: d.organizations for d in net.doctors}
    assert doctors["Dr. Ayesha Malik"] == ["City Hospital", "Clifton Family Clinic"]
    assert doctors["Dr. Arif Hassan"] == ["Clifton Medical Centre"]
    kinds = {o.organization.org_type for o in net.organizations}
    assert kinds == {"clinic", "hospital", "laboratory", "pharmacy"}


def test_provider_search_lists_doctor_organization_pairs(seeded):
    options = consent_service.search_providers(seeded, "arif")
    assert {(o.provider_name, o.organization_name) for o in options} == {
        ("Dr. Arif Hassan", "South City Hospital"), ("Dr. Arif Hassan", "Clifton Medical Centre")}
