"""The patient's longitudinal record — the ONLY path to read it.

Every public function authorizes through access_service, filters to the consented record
categories, and audits consent-based access. The private `_query_*` helpers do no checks and
must only be called after authorization.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import (
    BILLING_CATEGORY,
    ClinicalNote,
    Consultation,
    ConsultationStatus,
    Dispensing,
    Document,
    Invoice,
    LabOrder,
    LabOrderStatus,
    LabTestCategory,
    OrgType,
    Patient,
    PatientEntry,
    Prescription,
    PrescriptionStatus,
    RecordCategory,
    TimelineEvent,
    utcnow,
)
from core.schemas import (
    AccessDecision,
    Actor,
    AuthorizedRecord,
    ClinicalNoteOut,
    ConsultationOut,
    DispensingOut,
    DocumentOut,
    InvoiceOut,
    LabOrderOut,
    LabValueOut,
    MedicationOut,
    PatientEntryOut,
    PatientIdentity,
    PatientOut,
    PrescriptionItemOut,
    PrescriptionOut,
    TimelineEventOut,
)
from services import access_service, audit_service

NOT_ACTIVE = (PrescriptionStatus.DRAFT, PrescriptionStatus.REJECTED, PrescriptionStatus.CANCELLED)

# ---------------------------------------------------------------------------
# Record categories
# ---------------------------------------------------------------------------


def clinical_category(org_type: str) -> str:
    """Consultations and notes written at a hospital are 'hospital records'."""
    return RecordCategory.HOSPITAL_RECORDS if org_type == OrgType.HOSPITAL else RecordCategory.CONSULTATIONS


def lab_category(test_category: str) -> str:
    return RecordCategory.IMAGING_REPORTS if test_category == LabTestCategory.IMAGING else RecordCategory.LAB_REPORTS


# ---------------------------------------------------------------------------
# Converters (shared with role-specific services)
# ---------------------------------------------------------------------------


def consultation_to_out(c: Consultation) -> ConsultationOut:
    return ConsultationOut(
        id=c.id, patient_id=c.patient_id, patient_name=c.patient.name, provider_name=c.provider.name,
        organization_name=c.organization.name, organization_type=c.organization.org_type,
        record_category=clinical_category(c.organization.org_type), date=c.date, status=c.status,
        updated_at=c.updated_at, complaint=c.complaint,
        notes=c.notes, observations=c.observations, assessment=c.assessment, diagnosis=c.diagnosis,
        treatment_plan=c.treatment_plan, follow_up=c.follow_up,
    )


def note_to_out(n: ClinicalNote) -> ClinicalNoteOut:
    return ClinicalNoteOut(
        id=n.id, patient_id=n.patient_id, provider_name=n.provider.name, organization_name=n.organization.name,
        organization_type=n.organization.org_type, record_category=clinical_category(n.organization.org_type),
        consultation_id=n.consultation_id, note_type=n.note_type, content=n.content, created_at=n.created_at,
    )


def document_to_out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=d.id, patient_id=d.patient_id, source_type=d.source_type, uploaded_by_name=d.uploader.name,
        organization_name=d.organization.name if d.organization else None,
        organization_type=d.organization.org_type if d.organization else None, doc_type=d.doc_type,
        title=d.title, description=d.description, file_name=d.file_name, mime_type=d.mime_type,
        size_bytes=d.size_bytes, record_category=d.record_category, created_at=d.created_at,
        has_file=bool(d.storage_path), consultation_id=d.consultation_id,
    )


def invoice_to_out(i: Invoice) -> InvoiceOut:
    return InvoiceOut(
        id=i.id, invoice_number=i.invoice_number, prescription_id=i.prescription_id, patient_id=i.patient_id,
        patient_name=i.patient.name, pharmacy_name=i.organization.name, items=i.items, total=i.total,
        amount_paid=i.amount_paid, currency=i.currency, payment_status=i.payment_status, created_at=i.created_at,
    )


def dispensing_to_out(d: Dispensing) -> DispensingOut:
    return DispensingOut(id=d.id, pharmacist_name=d.pharmacist.name, pharmacy_name=d.organization.name,
                         dispensed_at=d.dispensed_at, status=d.status, items=d.items_dispensed,
                         substitutions=d.substitutions, notes=d.notes)


def prescription_to_out(rx: Prescription, include_reason: bool = True, include_invoice: bool = False) -> PrescriptionOut:
    p = PatientIdentity.model_validate(rx.patient)
    invoice = rx.invoices[-1] if include_invoice and rx.invoices else None
    return PrescriptionOut(
        id=rx.id, consultation_id=rx.consultation_id, patient_id=rx.patient_id, patient_name=p.name,
        patient_age=p.age, patient_sex=p.sex, patient_allergies=rx.patient.allergies,
        provider_name=rx.provider.name, organization_name=rx.organization.name,
        organization_type=rx.organization.org_type, pharmacy_name=rx.pharmacy.name if rx.pharmacy else None,
        status=rx.status, created_at=rx.created_at, issued_at=rx.issued_at, sent_at=rx.sent_at,
        dispensed_at=max((d.dispensed_at for d in rx.dispensings), default=None),
        reason=(rx.consultation.complaint if rx.consultation else None) if include_reason else None,
        notes=rx.notes, status_reason=rx.status_reason,
        items=[PrescriptionItemOut.model_validate(i) for i in rx.items],
        dispensings=[dispensing_to_out(d) for d in rx.dispensings],
        invoice=invoice_to_out(invoice) if invoice else None,
    )


def lab_to_out(o: LabOrder, include_unpublished_results: bool = False) -> LabOrderOut:
    r, rep = o.result, o.report
    show = r is not None and (o.status == LabOrderStatus.PUBLISHED or include_unpublished_results)
    return LabOrderOut(
        id=o.id, patient=PatientIdentity.model_validate(o.patient), provider_name=o.provider.name,
        organization_name=o.organization.name, organization_type=o.organization.org_type, lab_name=o.lab.name,
        test_name=o.test_name, test_category=o.test_category, record_category=lab_category(o.test_category),
        priority=o.priority, clinical_notes=o.clinical_notes, status=o.status, ordered_at=o.ordered_at,
        values=[LabValueOut(**v) for v in r.values] if show else [],
        interpretation=(rep.conclusion if rep and rep.conclusion else r.interpretation) if show else "",
        lab_notes=r.lab_notes if r and include_unpublished_results else "",
        entered_at=r.entered_at if r else None, verified_at=r.verified_at if r else None,
        published_at=rep.published_at if rep else None, report_number=rep.report_number if rep else None,
    )


def is_current(rx: PrescriptionOut, now=None) -> bool:
    if rx.status in NOT_ACTIVE:
        return False
    longest = max((i.duration_days for i in rx.items), default=0)
    return rx.created_at + timedelta(days=longest) >= (now or utcnow())


# ---------------------------------------------------------------------------
# Unchecked queries — call only after authorization
# ---------------------------------------------------------------------------


def _query_consultations(session: Session, patient_id: int, decision: AccessDecision) -> list[ConsultationOut]:
    # Drafts are private working copies of their author — never part of the shared clinical record.
    rows = session.scalars(select(Consultation).where(Consultation.patient_id == patient_id,
                                                      Consultation.status == ConsultationStatus.FINAL)
                           .order_by(Consultation.date.desc()))
    return [c for c in map(consultation_to_out, rows) if decision.can(c.record_category)]


def _query_notes(session: Session, patient_id: int, decision: AccessDecision) -> list[ClinicalNoteOut]:
    rows = session.scalars(select(ClinicalNote).where(ClinicalNote.patient_id == patient_id)
                           .order_by(ClinicalNote.created_at.desc()))
    return [n for n in map(note_to_out, rows) if decision.can(n.record_category)]


def _query_prescriptions(session: Session, patient_id: int, decision: AccessDecision) -> list[PrescriptionOut]:
    if not decision.can(RecordCategory.PRESCRIPTIONS):
        return []
    rows = session.scalars(select(Prescription).where(Prescription.patient_id == patient_id,
                                                      Prescription.status != PrescriptionStatus.DRAFT)
                           .order_by(Prescription.created_at.desc()))
    billing = decision.can(BILLING_CATEGORY)
    return [prescription_to_out(rx, include_invoice=billing) for rx in rows]


def _query_medications(session: Session, patient_id: int, decision: AccessDecision) -> list[MedicationOut]:
    if not decision.can(RecordCategory.MEDICATIONS):
        return []
    rows = session.scalars(select(Prescription).where(Prescription.patient_id == patient_id,
                                                      Prescription.status.notin_(NOT_ACTIVE))
                           .order_by(Prescription.created_at.desc()))
    meds = []
    for rx in map(prescription_to_out, rows):
        for i in rx.items:
            meds.append(MedicationOut(
                prescription_id=rx.id, drug_name=i.drug_name, strength=i.strength, dosage=i.dosage,
                frequency=i.frequency, started=rx.created_at,
                ends=rx.created_at + timedelta(days=i.duration_days), prescribed_by=rx.provider_name,
                organization_name=rx.organization_name, status=rx.status, current=is_current(rx),
            ))
    return meds


def _query_reports(session: Session, patient_id: int, decision: AccessDecision) -> list[LabOrderOut]:
    rows = session.scalars(select(LabOrder).where(LabOrder.patient_id == patient_id)
                           .order_by(LabOrder.ordered_at.desc()))
    return [o for o in map(lab_to_out, rows) if decision.can(o.record_category)]


def _query_documents(session: Session, patient_id: int, decision: AccessDecision) -> list[DocumentOut]:
    rows = session.scalars(select(Document).where(Document.patient_id == patient_id)
                           .order_by(Document.created_at.desc()))
    return [d for d in map(document_to_out, rows) if decision.can(d.record_category)]


def _query_patient_entries(session: Session, patient_id: int, decision: AccessDecision) -> list[PatientEntryOut]:
    if not decision.can(RecordCategory.DOCUMENTS):
        return []
    rows = session.scalars(select(PatientEntry).where(PatientEntry.patient_id == patient_id)
                           .order_by(PatientEntry.created_at.desc()))
    return [PatientEntryOut.model_validate(e) for e in rows]


def _query_timeline(session: Session, patient_id: int, decision: AccessDecision) -> list[TimelineEventOut]:
    rows = session.scalars(select(TimelineEvent).where(TimelineEvent.patient_id == patient_id)
                           .order_by(TimelineEvent.occurred_at.desc(), TimelineEvent.id.desc()))
    out = []
    for e in rows:
        if not decision.can(e.record_category):
            continue
        item = TimelineEventOut.model_validate(e)
        item.actor_name = e.actor.name if e.actor else None
        item.organization_name = e.organization.name if e.organization else None
        item.organization_type = e.organization.org_type if e.organization else None
        out.append(item)
    return out


def _patient_out(patient: Patient, decision: AccessDecision) -> PatientOut:
    # Allergies are shown with any active consent (safety-critical for prescribing);
    # diagnoses/conditions only when consultation or hospital records are shared.
    sees_conditions = decision.can(RecordCategory.CONSULTATIONS) or decision.can(RecordCategory.HOSPITAL_RECORDS)
    return PatientOut(id=patient.id, user_id=patient.user_id, name=patient.name, dob=patient.dob, sex=patient.sex,
                      allergies=patient.allergies, conditions=patient.conditions if sees_conditions else None)


# ---------------------------------------------------------------------------
# Public, access-controlled API
# ---------------------------------------------------------------------------


def get_authorized_record(session: Session, actor: Actor, patient_id: int, view: str = "patient_record") -> AuthorizedRecord:
    """The patient's record filtered to the viewer's consent scope. Raises AccessDenied otherwise."""
    decision = access_service.require(session, actor, patient_id)
    if decision.via == "consent":
        audit_service.log_record_access(session, actor, patient_id, view,
                                        decision.categories if decision.scope_type != "all" else "all",
                                        decision.consent_id)
    patient = session.get(Patient, patient_id)
    return AuthorizedRecord(
        patient=_patient_out(patient, decision), access=decision,
        consultations=_query_consultations(session, patient_id, decision),
        notes=_query_notes(session, patient_id, decision),
        prescriptions=_query_prescriptions(session, patient_id, decision),
        medications=_query_medications(session, patient_id, decision),
        reports=_query_reports(session, patient_id, decision),
        documents=_query_documents(session, patient_id, decision),
        patient_entries=_query_patient_entries(session, patient_id, decision),
        timeline=_query_timeline(session, patient_id, decision),
    )


def own_record(session: Session, actor: Actor) -> AuthorizedRecord:
    patient = session.scalar(select(Patient).where(Patient.user_id == actor.id))
    if patient is None:
        raise access_service.AccessDenied("No patient profile for this account")
    return get_authorized_record(session, actor, patient.id, view="own_record")
