"""Doctor-authored clinical records: consultations (draft → final) and clinical notes.

Rules
* Writing requires the same thing reading does: an active consent for this doctor at the
  organization they are working at (access_service.require).
* Organization context is taken from the acting context — never chosen by the doctor.
* Drafts are visible only to their author and never appear on the patient's timeline.
* Finalized consultations are immutable clinical records; additions are made with clinical notes.
"""

from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import AuditAction, ClinicalNote, Consultation, ConsultationStatus, EventType, NoteType, Role, utcnow
from core.schemas import Actor, ClinicalNoteOut, ConsultationOut
from services import access_service, activity_service, record_service

FIELDS = ("complaint", "notes", "observations", "assessment", "diagnosis", "treatment_plan", "follow_up",
          "additional_notes")
MAX_BACKDATE = timedelta(days=30)        # a consultation may be recorded after the visit, within reason
FUTURE_TOLERANCE = timedelta(minutes=5)


class ClinicalValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(errors.values()))
        self.errors = errors


class ConsultationInput(BaseModel):
    complaint: str = ""          # reason for visit
    notes: str = ""              # symptoms / clinical notes
    observations: str = ""
    assessment: str = ""
    diagnosis: str = ""
    treatment_plan: str = ""
    follow_up: str = ""
    additional_notes: str = ""   # patient-visible; for clinician-only text use an internal clinical note

    def cleaned(self) -> "ConsultationInput":
        return ConsultationInput(**{f: (getattr(self, f) or "").strip() for f in FIELDS})


def validate_visit_time(occurred_at: datetime | None) -> dict[str, str]:
    if occurred_at is None:
        return {}
    now = utcnow()
    if occurred_at > now + FUTURE_TOLERANCE:
        return {"occurred_at": "The consultation date/time cannot be in the future."}
    if occurred_at < now - MAX_BACKDATE:
        return {"occurred_at": "Consultations can be recorded up to 30 days after the visit."}
    return {}


def validate_for_finalize(data: ConsultationInput) -> dict[str, str]:
    errors = {}
    if not data.complaint:
        errors["complaint"] = "Reason for visit is required."
    if not (data.assessment or data.diagnosis):
        errors["assessment"] = "Add an assessment or a diagnosis before saving the consultation."
    return errors


def _require_doctor_access(session: Session, actor: Actor, patient_id: int):
    if actor.role != Role.DOCTOR or actor.organization_id is None:
        raise access_service.AccessDenied("Only doctors working at an organization can create clinical records")
    return access_service.require(session, actor, patient_id)


def _own_draft(session: Session, actor: Actor, consultation_id: int) -> Consultation:
    c = session.get(Consultation, consultation_id)
    if c is None or c.provider_id != actor.id or c.organization_id != actor.organization_id:
        raise access_service.AccessDenied("You can only edit your own drafts at this organization")
    if c.status != ConsultationStatus.DRAFT:
        raise ClinicalValidationError({"status": "This consultation is already finalized and cannot be edited. "
                                                 "Add a clinical note instead."})
    return c


def save_consultation(session: Session, actor: Actor, patient_id: int, data: ConsultationInput, *,
                      finalize: bool, consultation_id: int | None = None,
                      occurred_at: datetime | None = None) -> ConsultationOut:
    """Save a draft, or finalize (validate → clinical record → timeline + audit).

    occurred_at: when the visit took place (naive UTC); defaults to now. Patient, doctor and organization
    always come from the acting context — they cannot be overridden.
    """
    _require_doctor_access(session, actor, patient_id)
    data = data.cleaned()
    errors = validate_visit_time(occurred_at)
    if finalize:
        errors |= validate_for_finalize(data)
    if errors:
        raise ClinicalValidationError(errors)

    now = utcnow()
    if consultation_id:
        c = _own_draft(session, actor, consultation_id)
        if c.patient_id != patient_id:
            raise access_service.AccessDenied("Draft belongs to another patient")
    else:
        c = Consultation(patient_id=patient_id, provider_id=actor.id, organization_id=actor.organization_id,
                         status=ConsultationStatus.DRAFT, date=occurred_at or now)
        session.add(c)
    for f in FIELDS:
        setattr(c, f, getattr(data, f))
    if occurred_at:
        c.date = occurred_at
    c.updated_at = now
    session.flush()

    if finalize:
        c.status = ConsultationStatus.FINAL
        c.date = occurred_at or c.date or now
        session.flush()
        summary = f"{c.complaint} — {c.assessment or c.diagnosis}"
        activity_service.record(session, actor, patient_id=patient_id, event=EventType.CONSULTATION,
                                category=record_service.clinical_category(actor.organization.org_type),
                                resource_type="consultations", resource_id=c.id, summary=summary, when=c.date)
    else:
        activity_service.record(session, actor, patient_id=patient_id, event="consultation_draft_saved",
                                resource_type="consultations", resource_id=c.id, on_timeline=False,
                                action=AuditAction.RECORD_UPDATED if consultation_id else AuditAction.RECORD_CREATED)
    return record_service.consultation_to_out(c)


def get_consultation(session: Session, actor: Actor, consultation_id: int) -> ConsultationOut:
    """Authors always see their own consultations (incl. drafts); others need consent covering it."""
    c = session.get(Consultation, consultation_id)
    if c is None:
        raise access_service.AccessDenied("Consultation not found")
    out = record_service.consultation_to_out(c)
    if c.provider_id == actor.id and c.organization_id == actor.organization_id:
        return out
    if c.status == ConsultationStatus.DRAFT:
        raise access_service.AccessDenied("Drafts are private to their author")
    access_service.require(session, actor, c.patient_id, out.record_category)
    return out


def list_drafts(session: Session, actor: Actor) -> list[ConsultationOut]:
    if actor.role != Role.DOCTOR:
        return []
    rows = session.scalars(select(Consultation).where(
        Consultation.provider_id == actor.id, Consultation.organization_id == actor.organization_id,
        Consultation.status == ConsultationStatus.DRAFT).order_by(Consultation.updated_at.desc()))
    return [record_service.consultation_to_out(c) for c in rows]


def discard_draft(session: Session, actor: Actor, consultation_id: int) -> None:
    c = _own_draft(session, actor, consultation_id)
    activity_service.record(session, actor, patient_id=c.patient_id, event="consultation_draft_discarded",
                            resource_type="consultations", resource_id=c.id, on_timeline=False,
                            action=AuditAction.RECORD_UPDATED)
    session.delete(c)
    session.flush()


# ---------------------------------------------------------------------------
# Clinical notes
# ---------------------------------------------------------------------------


def add_note(session: Session, actor: Actor, patient_id: int, note_type: str, content: str,
             consultation_id: int | None = None) -> ClinicalNoteOut:
    _require_doctor_access(session, actor, patient_id)
    content = (content or "").strip()
    if not content:
        raise ClinicalValidationError({"content": "The note cannot be empty."})
    note_type = NoteType(note_type)
    if consultation_id:
        c = session.get(Consultation, consultation_id)
        if c is None or c.patient_id != patient_id or c.status != ConsultationStatus.FINAL:
            raise ClinicalValidationError({"consultation": "Notes can only be attached to a finalized consultation."})
    n = ClinicalNote(patient_id=patient_id, provider_id=actor.id, organization_id=actor.organization_id,
                     consultation_id=consultation_id, note_type=note_type, content=content, created_at=utcnow())
    session.add(n)
    session.flush()
    # Internal clinician notes: on the clinical timeline for authorized clinicians, never shown to the patient.
    activity_service.record(session, actor, patient_id=patient_id, event=EventType.CLINICAL_NOTE,
                            category=record_service.clinical_category(actor.organization.org_type),
                            resource_type="clinical_notes", resource_id=n.id, summary=content, when=n.created_at,
                            patient_visible=note_type != NoteType.INTERNAL)
    return record_service.note_to_out(n)


def notes_for_consultation(session: Session, actor: Actor, consultation_id: int) -> list[ClinicalNoteOut]:
    get_consultation(session, actor, consultation_id)  # authorizes
    stmt = select(ClinicalNote).where(ClinicalNote.consultation_id == consultation_id)
    if actor.role == Role.PATIENT:
        stmt = stmt.where(ClinicalNote.note_type != NoteType.INTERNAL)
    rows = session.scalars(stmt.order_by(ClinicalNote.created_at))
    return [record_service.note_to_out(n) for n in rows]
