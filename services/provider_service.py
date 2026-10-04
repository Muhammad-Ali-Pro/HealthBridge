"""A doctor's own work: records they authored, and the organizations they work at.

Authored-record lists show only what this provider created (their own clinical work), never
other providers' records — reading a patient's wider record goes through record_service.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from core.models import (
    Consent,
    ConsentStatus,
    Consultation,
    ConsultationStatus,
    Document,
    LabOrder,
    Patient,
    Prescription,
    PrescriptionStatus,
    Role,
    local_day_start_utc,
    utcnow,
)
from core.schemas import (
    AccessDecision,
    Actor,
    ConsultationOut,
    DocumentOut,
    LabOrderOut,
    MembershipOut,
    PatientIdentity,
    PrescriptionOut,
)
from services import access_service, record_service, user_service


def start_of_today() -> datetime:
    """Start of the user's local day (naive UTC), so 'today' matches the times shown in the UI."""
    return local_day_start_utc()


def _require_doctor(actor: Actor) -> None:
    if actor.role != Role.DOCTOR:
        raise access_service.AccessDenied("Doctors only")


def my_consultations(session: Session, actor: Actor, *, today_only: bool = False,
                     this_org_only: bool = False, limit: int | None = None) -> list[ConsultationOut]:
    """Finalized consultations this doctor authored (drafts: clinical_service.list_drafts)."""
    _require_doctor(actor)
    stmt = select(Consultation).where(Consultation.provider_id == actor.id,
                                      Consultation.status == ConsultationStatus.FINAL)
    if this_org_only:
        stmt = stmt.where(Consultation.organization_id == actor.organization_id)
    if today_only:
        stmt = stmt.where(Consultation.date >= start_of_today())
    return [record_service.consultation_to_out(c) for c in
            session.scalars(stmt.order_by(Consultation.date.desc()).limit(limit))]


def todays_consultations(session: Session, actor: Actor) -> list[ConsultationOut]:
    """Today at this organization — finalized and draft — newest first."""
    _require_doctor(actor)
    today = start_of_today()
    rows = session.scalars(select(Consultation).where(
        Consultation.provider_id == actor.id, Consultation.organization_id == actor.organization_id,
        or_(Consultation.date >= today,
            and_(Consultation.status == ConsultationStatus.DRAFT, Consultation.updated_at >= today)),
    ).order_by(Consultation.date.desc()))
    return [record_service.consultation_to_out(c) for c in rows]


@dataclass
class RecentPatient:
    patient: PatientIdentity
    last_interaction: datetime
    activity: str                 # "Consultation" / "Prescription"
    organization_name: str
    organization_type: str
    access: AccessDecision        # at the doctor's CURRENT organization


def recent_patients(session: Session, actor: Actor, limit: int = 5) -> list[RecentPatient]:
    """Patients this doctor recently documented care for (their own work only) with current access status.

    Identity + where the doctor last saw them; no clinical content. Access is re-evaluated for the organization
    the doctor is working at now, so a patient seen elsewhere may show as restricted here.
    """
    _require_doctor(actor)
    latest: dict[int, tuple[datetime, str, object]] = {}
    for c in session.scalars(select(Consultation).where(Consultation.provider_id == actor.id,
                                                        Consultation.status == ConsultationStatus.FINAL)):
        if c.patient_id not in latest or c.date > latest[c.patient_id][0]:
            latest[c.patient_id] = (c.date, "Consultation", c.organization)
    for rx in session.scalars(select(Prescription).where(Prescription.provider_id == actor.id,
                                                         Prescription.issued_at.is_not(None))):
        if rx.patient_id not in latest or rx.issued_at > latest[rx.patient_id][0]:
            latest[rx.patient_id] = (rx.issued_at, "Prescription", rx.organization)
    ordered = sorted(latest.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    return [RecentPatient(patient=PatientIdentity.model_validate(session.get(Patient, pid)), last_interaction=when,
                          activity=what, organization_name=org.name, organization_type=org.org_type,
                          access=access_service.authorize(session, actor, pid))
            for pid, (when, what, org) in ordered]


def my_prescriptions(session: Session, actor: Actor, *, limit: int | None = None,
                     include_drafts: bool = False) -> list[PrescriptionOut]:
    """Prescriptions this doctor wrote. Drafts are private and only included for this organization."""
    _require_doctor(actor)
    stmt = select(Prescription).where(Prescription.provider_id == actor.id)
    if include_drafts:
        stmt = stmt.where((Prescription.status != PrescriptionStatus.DRAFT)
                          | (Prescription.organization_id == actor.organization_id))
    else:
        stmt = stmt.where(Prescription.status != PrescriptionStatus.DRAFT)
    stmt = stmt.order_by(Prescription.created_at.desc()).limit(limit)
    return [record_service.prescription_to_out(rx) for rx in session.scalars(stmt)]


def pending_follow_ups(session: Session, actor: Actor, days: int = 30) -> list[ConsultationOut]:
    """Recent finalized consultations here with follow-up instructions — the doctor's follow-up list."""
    _require_doctor(actor)
    since = utcnow() - timedelta(days=days)
    rows = session.scalars(select(Consultation).where(
        Consultation.provider_id == actor.id, Consultation.organization_id == actor.organization_id,
        Consultation.status == ConsultationStatus.FINAL, Consultation.follow_up != "", Consultation.date >= since,
    ).order_by(Consultation.date.desc()))
    return [record_service.consultation_to_out(c) for c in rows]


def my_lab_orders(session: Session, actor: Actor) -> list[LabOrderOut]:
    """Tests this doctor ordered at the acting organization; the ordering provider receives the results."""
    _require_doctor(actor)
    rows = session.scalars(select(LabOrder).where(LabOrder.provider_id == actor.id,
                                                  LabOrder.organization_id == actor.organization_id)
                           .order_by(LabOrder.ordered_at.desc()))
    return [record_service.lab_to_out(o) for o in rows]


def my_documents(session: Session, actor: Actor) -> list[DocumentOut]:
    """Documents this doctor uploaded (at any of their organizations)."""
    _require_doctor(actor)
    rows = session.scalars(select(Document).where(Document.uploaded_by == actor.id).order_by(Document.created_at.desc()))
    return [record_service.document_to_out(d) for d in rows]


def my_organizations(session: Session, actor: Actor) -> list[tuple[MembershipOut, dict[str, int]]]:
    _require_doctor(actor)
    out = []
    for m in user_service.memberships(session, actor.id):
        org_id = m.organization.id
        consults = session.scalar(select(func.count()).select_from(Consultation).where(
            Consultation.provider_id == actor.id, Consultation.organization_id == org_id))
        consents = session.scalars(select(Consent).where(
            Consent.provider_id == actor.id, Consent.organization_id == org_id,
            Consent.status == ConsentStatus.ACTIVE))
        active = sum(access_service.effective_status(session, c) == ConsentStatus.ACTIVE for c in consents)
        out.append((m, {"consultations": consults, "patients_with_access": active}))
    return out
