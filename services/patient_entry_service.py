"""Patient-provided information: notes, allergies and other entries the patient adds to their own record.

* Append-only (D15): entries can be added, never edited or deleted — corrections are new entries.
* Always labelled patient-provided (`source_type="patient"`); never verified by a clinician.
* A patient-reported allergy is a `PatientEntry(entry_type="allergy")`; it never changes the
  clinician-documented `Patient.allergies` list (D2).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import EventType, Patient, PatientEntry, PatientEntryType, RecordCategory, Role, utcnow
from core.schemas import Actor, PatientEntryOut
from services import access_service, activity_service
from services.clinical_service import ClinicalValidationError

TITLE_MAX = 200
DETAILS_MAX = 2000
ENTRY_LABELS = {
    PatientEntryType.NOTE: "Health note",
    PatientEntryType.ALLERGY: "Allergy",
    PatientEntryType.CONDITION: "Condition",
    PatientEntryType.MEDICATION: "Medication I take",
    PatientEntryType.OTHER: "Other information",
}


def own_patient(session: Session, actor: Actor) -> Patient:
    """The acting patient's own Patient row (or AccessDenied for any other role)."""
    patient = session.scalar(select(Patient).where(Patient.user_id == actor.id)) if actor.role == Role.PATIENT else None
    if patient is None:
        raise access_service.AccessDenied("Only patients can add information to their own record")
    access_service.require_self(session, actor, patient.id)
    return patient


def validate(entry_type: str, title: str, details: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    if entry_type not in {t.value for t in PatientEntryType}:
        errors["entry_type"] = "Choose what you are adding."
    title = (title or "").strip()
    if not title:
        errors["title"] = "Please add a short title." if entry_type != PatientEntryType.ALLERGY else "What are you allergic to?"
    elif len(title) > TITLE_MAX:
        errors["title"] = f"Keep the title under {TITLE_MAX} characters."
    if len((details or "").strip()) > DETAILS_MAX:
        errors["details"] = f"Keep the details under {DETAILS_MAX} characters."
    return errors


def add_entry(session: Session, actor: Actor, entry_type: str, title: str, details: str = "") -> PatientEntryOut:
    patient = own_patient(session, actor)
    errors = validate(entry_type, title, details)
    if errors:
        raise ClinicalValidationError(errors)
    entry_type, title, details = PatientEntryType(entry_type), title.strip(), (details or "").strip()
    now = utcnow()
    entry = PatientEntry(patient_id=patient.id, entry_type=entry_type, title=title, details=details, created_at=now)
    session.add(entry)
    session.flush()
    label = "Allergy reported" if entry_type == PatientEntryType.ALLERGY else ENTRY_LABELS[entry_type]
    activity_service.record(session, actor, patient_id=patient.id, event=EventType.PATIENT_ENTRY,
                            category=RecordCategory.DOCUMENTS, resource_type="patient_entries", resource_id=entry.id,
                            summary=f"{label}: {title}", when=now, details={"entry_type": entry_type})
    return PatientEntryOut.model_validate(entry)


def reported_allergies(session: Session, patient_id: int) -> list[str]:
    """Patient-reported allergy titles (callers must already have authorized access to this patient)."""
    rows = session.scalars(select(PatientEntry.title).where(PatientEntry.patient_id == patient_id,
                                                            PatientEntry.entry_type == PatientEntryType.ALLERGY)
                           .order_by(PatientEntry.created_at))
    return list(dict.fromkeys(rows))
