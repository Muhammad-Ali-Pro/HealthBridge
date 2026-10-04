"""Phase 2 additions: pharmacy handoff, AI flag review + view source, internal notes, consultation timing,
multi-agent retrieval scope, and the new dashboard KPIs."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from agents import retrieval
from agents.providers import AIProvider, AIUnavailable, ConnectionResult
from core.models import AIFlag, AuditAction, AuditLog, Organization, TimelineEvent, utcnow
from services import (
    access_service,
    audit_service,
    clinical_service,
    consent_service,
    copilot_service,
    dashboard_service,
    insight_service,
    pharmacy_service,
    provider_service,
    prescription_service,
    record_service,
)
from services.access_service import AccessDenied
from services.clinical_service import ClinicalValidationError, ConsultationInput
from services.prescription_service import MedicineInput

VISIT = ConsultationInput(complaint="Exertional chest tightness", assessment="Possible stable angina",
                          diagnosis="Chest pain", follow_up="Review in 1 week", additional_notes="Patient brought ECG copy")
METFORMIN = MedicineInput(drug_name="Metformin", strength="500 mg", dosage="1 tablet", frequency="twice daily",
                          duration_days=30, quantity=60)


def org(seeded, name):
    return seeded.scalar(select(Organization.id).where(Organization.name == name))


@pytest.fixture
def arif(seeded, actor):
    """Ahmed → Dr. Arif @ South City: consultations, prescriptions, current medications (the demo consent)."""
    consent_service.grant(seeded, actor("Ahmed Khan"), provider_id=actor("Dr. Arif Hassan").id,
                          organization_id=org(seeded, "South City Hospital"), scope_type="selected",
                          categories=["consultations", "prescriptions", "medications"])
    return actor("Dr. Arif Hassan")


@pytest.fixture
def ahmed(actor):
    return actor("Ahmed Khan")


def issued_rx(seeded, doctor, pid):
    c = clinical_service.save_consultation(seeded, doctor, pid, VISIT, finalize=True)
    rx = prescription_service.save_draft(seeded, doctor, pid, [METFORMIN], consultation_id=c.id)
    return prescription_service.issue(seeded, doctor, rx.id)


# 1. Prescription → selected pharmacy → SENT ---------------------------------------------------


def test_prescription_sent_to_selected_pharmacy(seeded, arif, actor, pid):
    rx = issued_rx(seeded, arif, pid("Ahmed Khan"))
    healthplus = org(seeded, "HealthPlus Pharmacy")
    assert healthplus in [p.id for p in prescription_service.available_pharmacies(seeded)]
    sent = prescription_service.send_to_pharmacy(seeded, arif, rx.id, healthplus)
    assert sent.status == "sent" and sent.pharmacy_name == "HealthPlus Pharmacy" and sent.sent_at is not None
    # Handoff only: it lands in the pharmacy's queue awaiting verification (Phase 3 does the rest).
    queue = pharmacy_service.list_prescriptions(seeded, actor("Sana Iqbal"), pharmacy_service.AWAITING)
    assert rx.id in [q.id for q in queue]
    ev = seeded.scalars(select(TimelineEvent).where(TimelineEvent.ref_id == rx.id,
                                                    TimelineEvent.event_type == "prescription_sent")).one()
    assert ev.organization_id == arif.organization_id and ev.actor_id == arif.id
    assert "HealthPlus Pharmacy" in ev.summary


def test_pharmacy_handoff_rules(seeded, arif, actor, pid):
    ahmed_id = pid("Ahmed Khan")
    draft = prescription_service.save_draft(seeded, arif, ahmed_id, [METFORMIN])
    with pytest.raises(ClinicalValidationError):  # drafts cannot be sent
        prescription_service.send_to_pharmacy(seeded, arif, draft.id, org(seeded, "HealthPlus Pharmacy"))
    rx = issued_rx(seeded, arif, ahmed_id)
    with pytest.raises(ClinicalValidationError):  # a clinic is not a pharmacy
        prescription_service.send_to_pharmacy(seeded, arif, rx.id, org(seeded, "Clifton Family Clinic"))
    with pytest.raises(AccessDenied):  # only the prescriber, at the prescribing organization
        prescription_service.send_to_pharmacy(seeded, actor("Dr. Arif Hassan", "Clifton Medical Centre"), rx.id,
                                              org(seeded, "HealthPlus Pharmacy"))
    prescription_service.send_to_pharmacy(seeded, arif, rx.id, org(seeded, "HealthPlus Pharmacy"))
    with pytest.raises(ClinicalValidationError):  # cannot be sent twice
        prescription_service.send_to_pharmacy(seeded, arif, rx.id, org(seeded, "CarePoint Pharmacy"))


# 2. AI flags: accept / dismiss / view source ---------------------------------------------------


def test_safety_agent_flags_are_stored_scoped_and_reviewable(seeded, arif, actor, pid):
    ahmed_id = pid("Ahmed Khan")
    # A consultation without diagnosis / follow-up gives the Safety agent a second, "missing information" flag.
    clinical_service.save_consultation(seeded, arif, ahmed_id, ConsultationInput(complaint="Cough", assessment="Viral"),
                                       finalize=True)
    result = copilot_service.generate(seeded, arif, ahmed_id, provider=None)
    items = result.summary.items_for_review
    assert {"medication_discrepancy", "missing_information"} <= {i.category for i in items}
    assert items and all(i.flag_id and i.severity and i.category and i.issue and i.sources for i in items)
    med = next(i for i in items if i.category == "medication_discrepancy")
    flag = seeded.get(AIFlag, med.flag_id)
    assert (flag.requested_by, flag.organization_id, flag.summary_id) == (arif.id, arif.organization_id, result.summary_id)
    assert flag.sources == med.sources and flag.status == "open"
    assert dashboard_service.doctor_kpis(seeded, arif)["ai_review_items"] == len(items)

    accepted = copilot_service.review_flag(seeded, arif, med.flag_id, "accepted")
    assert accepted.status == "accepted" and accepted.reviewed_by_name == "Dr. Arif Hassan" and accepted.reviewed_at
    other = next(i for i in items if i.flag_id != med.flag_id)
    assert copilot_service.review_flag(seeded, arif, other.flag_id, "dismissed", "Known; documented").status == "dismissed"
    assert seeded.scalars(select(AuditLog).where(AuditLog.action == AuditAction.AI_FLAG_REVIEWED)).all()
    assert dashboard_service.doctor_kpis(seeded, arif)["ai_review_items"] == len(items) - 2

    # Another clinician, or the same doctor at another organization, cannot see or review these flags.
    with pytest.raises(AccessDenied):
        copilot_service.review_flag(seeded, actor("Dr. Ayesha Malik"), med.flag_id, "dismissed")
    assert insight_service.list_flags(seeded, actor("Dr. Arif Hassan", "Clifton Medical Centre")) == []


def test_view_source_resolves_records_through_consent(seeded, arif, ahmed, pid):
    ahmed_id = pid("Ahmed Khan")
    result = copilot_service.generate(seeded, arif, ahmed_id, provider=None)
    med = next(i for i in result.summary.items_for_review if i.category == "medication_discrepancy")
    details = copilot_service.resolve_sources(seeded, arif, ahmed_id, med.sources + ["LAB-00001", "DOC-1"])
    rx_details = [d for d in details if d.record_type == "Prescription"]
    assert len(rx_details) == 2 and all(d.organization_name and d.provider_name and d.date for d in rx_details)
    assert {"850 mg" in d.excerpt or "500 mg" in d.excerpt for d in rx_details} == {True}
    # Records outside the consent scope are never resolved.
    assert [d.available for d in details[-2:]] == [False, False]
    consent_service.revoke(seeded, ahmed, access_service.authorize(seeded, arif, ahmed_id).consent_id)
    with pytest.raises(AccessDenied):
        copilot_service.resolve_sources(seeded, arif, ahmed_id, med.sources)


# 3. Internal clinician notes ----------------------------------------------------------------------


def test_internal_notes_never_reach_the_patient(seeded, arif, ahmed, pid):
    ahmed_id = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif, ahmed_id, VISIT, finalize=True)
    internal = clinical_service.add_note(seeded, arif, ahmed_id, "internal", "Query adherence — discuss privately.",
                                         consultation_id=c.id)
    shared = clinical_service.add_note(seeded, arif, ahmed_id, "follow_up", "Bring home BP readings.", consultation_id=c.id)

    doctor_view = record_service.get_authorized_record(seeded, arif, ahmed_id)
    assert {internal.id, shared.id} <= {n.id for n in doctor_view.notes}
    assert any(not e.patient_visible for e in doctor_view.timeline)

    own = record_service.own_record(seeded, ahmed)
    assert internal.id not in {n.id for n in own.notes} and shared.id in {n.id for n in own.notes}
    assert all("Query adherence" not in e.summary for e in own.timeline)
    assert [n.id for n in clinical_service.notes_for_consultation(seeded, ahmed, c.id)] == [shared.id]
    history = audit_service.patient_history(seeded, ahmed, ahmed_id, include_activity=True)
    assert all("Query adherence" not in str(e.details) for e in history)
    assert all(e.resource_id != internal.id or e.resource_type != "clinical_notes" for e in history)


# 4. Consultation: editable visit time, additional notes, provenance --------------------------------


def test_consultation_visit_time_additional_notes_and_provenance(seeded, arif, ahmed, pid):
    ahmed_id = pid("Ahmed Khan")
    visit = utcnow().replace(microsecond=0) - timedelta(days=2, hours=3)
    c = clinical_service.save_consultation(seeded, arif, ahmed_id, VISIT, finalize=True, occurred_at=visit)
    assert c.date == visit and c.additional_notes == "Patient brought ECG copy"
    assert (c.provider_name, c.organization_name) == ("Dr. Arif Hassan", "South City Hospital")
    ev = seeded.scalars(select(TimelineEvent).where(TimelineEvent.ref_table == "consultations",
                                                    TimelineEvent.ref_id == c.id)).one()
    assert ev.occurred_at == visit and ev.organization_id == arif.organization_id
    assert c.id in {x.id for x in record_service.own_record(seeded, ahmed).consultations}
    with pytest.raises(ClinicalValidationError) as future:
        clinical_service.save_consultation(seeded, arif, ahmed_id, VISIT, finalize=True,
                                           occurred_at=utcnow() + timedelta(hours=2))
    assert "future" in future.value.errors["occurred_at"]
    with pytest.raises(ClinicalValidationError):
        clinical_service.save_consultation(seeded, arif, ahmed_id, VISIT, finalize=True,
                                           occurred_at=utcnow() - timedelta(days=45))


# 5. Multi-agent copilot: retrieval scope + organization context ------------------------------------


class CapturingLLM(AIProvider):
    label = "Capturing provider"

    def __init__(self):
        self.payloads: list[str] = []

    def get_model_name(self) -> str:
        return "capture"

    def test_connection(self) -> ConnectionResult:
        return ConnectionResult(True, "ok", "capture")

    def generate_structured(self, system: str, user: str, schema) -> dict:
        self.payloads.append(user)
        raise AIUnavailable("network")  # capture what would be sent, then fall back


def test_same_doctor_two_organizations_different_consent_states(seeded, arif, actor, pid):
    ahmed_id = pid("Ahmed Khan")
    llm = CapturingLLM()
    result = copilot_service.generate(seeded, arif, ahmed_id, provider=llm)
    assert result.retrieval["labs"] == 0 and result.retrieval["documents"] == 0  # not consented → empty
    assert result.retrieval["consultations"] > 0 and result.retrieval["prescriptions"] > 0
    assert llm.payloads and "LAB-" not in llm.payloads[0] and "HealthLab" not in llm.payloads[0]

    at_cmc = actor("Dr. Arif Hassan", "Clifton Medical Centre")
    other = CapturingLLM()
    with pytest.raises(AccessDenied):
        copilot_service.generate(seeded, at_cmc, ahmed_id, provider=other)
    assert other.payloads == []  # no agent ran, nothing left the consent boundary
    with pytest.raises(AccessDenied):
        copilot_service.preview(seeded, at_cmc, ahmed_id)


def test_record_retrieval_agent_rejects_out_of_scope_records(seeded, actor, pid):
    ayesha = actor("Dr. Ayesha Malik")
    fatima_record = record_service.get_authorized_record(seeded, ayesha, pid("Fatima Raza"))

    class WrongPatientSource:  # a handle claiming Ahmed but returning someone else's record
        patient_id, provider_id, organization_id = pid("Ahmed Khan"), ayesha.id, ayesha.organization_id

        def fetch(self):
            return fatima_record

    with pytest.raises(retrieval.RetrievalViolation):
        retrieval.retrieve(WrongPatientSource())


def test_summary_marks_missing_information_and_keeps_sources(seeded, arif, pid):
    result = copilot_service.generate(seeded, arif, pid("Ahmed Khan"), provider=None)
    assert result.summary.important_reports == []  # labs not consented → nothing invented
    assert result.summary.important_changes and result.summary.follow_up
    known = {s.id for s in result.sources}
    for item in result.summary.recent_history + result.summary.important_changes + result.summary.follow_up:
        assert item.sources and set(item.sources) <= known


# 6. Dashboard KPIs -----------------------------------------------------------------------------------


def test_dashboard_counts_issued_prescriptions(seeded, arif, pid):
    before = dashboard_service.doctor_kpis(seeded, arif)["prescriptions_issued_30d"]
    issued_rx(seeded, arif, pid("Ahmed Khan"))
    assert dashboard_service.doctor_kpis(seeded, arif)["prescriptions_issued_30d"] == before + 1


# 7. Spec example prescription, dashboard panels, consent-aware timeline filters ---------------------


def test_multi_medicine_prescription_keeps_every_field_through_send(seeded, arif, pid):
    ahmed_id = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif, ahmed_id, VISIT, finalize=True)
    amoxicillin = MedicineInput(drug_name="Amoxicillin", strength="500 mg", dosage="1 capsule", frequency="3 times daily",
                                duration_days=5, quantity=15, instructions="After meals")
    draft = prescription_service.save_draft(seeded, arif, ahmed_id, [amoxicillin, METFORMIN], notes="Review in 1 week",
                                            consultation_id=c.id)
    # Edit: remove Metformin, change the Amoxicillin quantity — same draft id.
    edited = prescription_service.save_draft(seeded, arif, ahmed_id, [amoxicillin.model_copy(update={"quantity": 15})],
                                             consultation_id=c.id, prescription_id=draft.id)
    assert edited.id == draft.id and [i.drug_name for i in edited.items] == ["Amoxicillin"]
    draft = prescription_service.save_draft(seeded, arif, ahmed_id, [amoxicillin, METFORMIN], consultation_id=c.id,
                                            prescription_id=draft.id)
    issued = prescription_service.issue(seeded, arif, draft.id)
    sent = prescription_service.send_to_pharmacy(seeded, arif, issued.id, org(seeded, "HealthPlus Pharmacy"))
    amox = next(i for i in sent.items if i.drug_name == "Amoxicillin")
    assert (amox.strength, amox.dosage, amox.frequency, amox.duration_days, amox.quantity, amox.instructions) == (
        "500 mg", "1 capsule", "3 times daily", 5, 15, "After meals")
    assert len(sent.items) == 2 and sent.status == "sent" and sent.pharmacy_name == "HealthPlus Pharmacy"
    assert sent.provider_name == "Dr. Arif Hassan" and sent.organization_name == "South City Hospital"


def test_dashboard_recent_patients_and_todays_consultations(seeded, arif, actor, pid):
    ahmed_id = pid("Ahmed Khan")
    c = clinical_service.save_consultation(seeded, arif, ahmed_id, VISIT, finalize=True)
    today = provider_service.todays_consultations(seeded, arif)
    assert c.id in [t.id for t in today]
    row = next(t for t in today if t.id == c.id)
    assert (row.patient_name, row.organization_name, row.complaint, row.status) == (
        "Ahmed Khan", "South City Hospital", "Exertional chest tightness", "final")

    recent = provider_service.recent_patients(seeded, arif)
    assert recent[0].patient.name == "Ahmed Khan" and recent[0].access.allowed
    assert recent[0].organization_name == "South City Hospital"
    assert not hasattr(recent[0].patient, "allergies")                         # identity only
    # Same doctor, other organization: today's list is per organization, access is re-evaluated there.
    at_cmc = actor("Dr. Arif Hassan", "Clifton Medical Centre")
    assert c.id not in [t.id for t in provider_service.todays_consultations(seeded, at_cmc)]
    there = next(r for r in provider_service.recent_patients(seeded, at_cmc) if r.patient.name == "Ahmed Khan")
    assert not there.access.allowed


def test_timeline_filters_offer_only_consented_categories(seeded, arif, ahmed, pid):
    from ui.components import authorized_filters

    record = record_service.get_authorized_record(seeded, arif, pid("Ahmed Khan"))
    offered, locked = authorized_filters(record.access)
    assert offered == ["All", "Consultations", "Prescriptions", "Pharmacy"]
    assert locked == ["Labs", "Hospital", "Documents"]
    assert authorized_filters(record_service.own_record(seeded, ahmed).access)[1] == []   # patient sees all
