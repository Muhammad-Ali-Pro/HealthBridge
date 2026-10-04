"""Documents: provider uploads (PDF/PNG/JPG, stored locally for the MVP) and consent-checked reads."""

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.models import (
    Consultation,
    Document,
    DocumentType,
    EventType,
    Patient,
    RecordCategory,
    Role,
    SourceType,
    utcnow,
)
from core.schemas import Actor, DocumentOut, PatientIdentity
from services import access_service, activity_service, audit_service, patient_service, record_service
from services.clinical_service import ClinicalValidationError

ALLOWED_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MAX_BYTES = 10 * 1024 * 1024


def _upload_dir() -> Path:
    return Path(settings.upload_dir)


def _validate(session: Session, patient_id: int, *, file_name: str, data: bytes, doc_type: str, title: str,
              consultation_id: int | None) -> str:
    """Shared upload rules (doctor and patient). Returns the lower-case extension."""
    ext = Path(file_name or "").suffix.lower()
    errors = {}
    if ext not in ALLOWED_TYPES:
        errors["file"] = "Only PDF, PNG or JPG files are supported."
    if not data:
        errors["file"] = "The file is empty."
    elif len(data) > MAX_BYTES:
        errors["file"] = "Files must be 10 MB or smaller."
    if not (title or "").strip():
        errors["title"] = "Give the document a title."
    elif len(title.strip()) > 200:
        errors["title"] = "Keep the title under 200 characters."
    if doc_type not in {t.value for t in DocumentType}:
        errors["doc_type"] = "Choose a document type."
    if consultation_id:
        c = session.get(Consultation, consultation_id)
        if c is None or c.patient_id != patient_id:
            errors["consultation"] = "Attachment must belong to this patient's consultation."
    if errors:
        raise ClinicalValidationError(errors)
    return ext


def _store(patient_id: int, ext: str, data: bytes) -> str:
    folder = _upload_dir() / f"patient_{patient_id}"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{ext}"
    stored.write_bytes(data)
    return str(stored)


def upload(session: Session, actor: Actor, patient_id: int, *, file_name: str, data: bytes, doc_type: str,
           title: str, description: str = "", consultation_id: int | None = None) -> DocumentOut:
    """A doctor adds a document to a consented patient's record (provider source)."""
    if actor.role != Role.DOCTOR or actor.organization_id is None:
        raise access_service.AccessDenied("Only doctors working at an organization can upload documents here")
    access_service.require(session, actor, patient_id)
    ext = _validate(session, patient_id, file_name=file_name, data=data, doc_type=doc_type, title=title,
                    consultation_id=consultation_id)
    d = Document(patient_id=patient_id, source_type=SourceType.PROVIDER, uploaded_by=actor.id,
                 organization_id=actor.organization_id, doc_type=DocumentType(doc_type), title=title.strip(),
                 description=(description or "").strip(), file_name=Path(file_name).name, mime_type=ALLOWED_TYPES[ext],
                 size_bytes=len(data), storage_path=_store(patient_id, ext, data), record_category=RecordCategory.DOCUMENTS,
                 consultation_id=consultation_id, created_at=utcnow())
    session.add(d)
    session.flush()
    activity_service.record(session, actor, patient_id=patient_id, event=EventType.DOCUMENT_ADDED,
                            category=RecordCategory.DOCUMENTS, resource_type="documents", resource_id=d.id,
                            summary=f"{d.title} uploaded", when=d.created_at)
    return record_service.document_to_out(d)


def upload_own(session: Session, actor: Actor, *, file_name: str, data: bytes, doc_type: str, title: str,
               description: str = "") -> DocumentOut:
    """The patient adds a document to their own record — always marked patient-provided."""
    from services.patient_entry_service import own_patient  # local import: avoids a service import cycle

    patient = own_patient(session, actor)
    ext = _validate(session, patient.id, file_name=file_name, data=data, doc_type=doc_type, title=title,
                    consultation_id=None)
    d = Document(patient_id=patient.id, source_type=SourceType.PATIENT, uploaded_by=actor.id, organization_id=None,
                 doc_type=DocumentType(doc_type), title=title.strip(), description=(description or "").strip(),
                 file_name=Path(file_name).name, mime_type=ALLOWED_TYPES[ext], size_bytes=len(data),
                 storage_path=_store(patient.id, ext, data), record_category=RecordCategory.DOCUMENTS,
                 created_at=utcnow())
    session.add(d)
    session.flush()
    activity_service.record(session, actor, patient_id=patient.id, event=EventType.DOCUMENT_ADDED,
                            category=RecordCategory.DOCUMENTS, resource_type="documents", resource_id=d.id,
                            summary=f"{d.title} uploaded by you", when=d.created_at, details={"doc_type": d.doc_type})
    return record_service.document_to_out(d)


def _can_read(session: Session, actor: Actor, d: Document) -> bool:
    decision = access_service.authorize(session, actor, d.patient_id)
    if not decision.allowed:
        return False          # revoked/expired consent hides even documents this doctor uploaded
    if d.uploaded_by == actor.id and (decision.via == "self" or d.organization_id == actor.organization_id):
        return True
    return decision.can(d.record_category)


def read_file(session: Session, actor: Actor, document_id: int) -> tuple[bytes, str, str]:
    d = session.get(Document, document_id)
    if d is None or not _can_read(session, actor, d):
        raise access_service.AccessDenied("You are not authorized to open this document")
    if not d.storage_path or not Path(d.storage_path).exists():
        raise FileNotFoundError("No file is stored for this demo document")
    return Path(d.storage_path).read_bytes(), d.file_name or "document", d.mime_type or "application/octet-stream"


def for_consultation(session: Session, actor: Actor, consultation_id: int) -> list[DocumentOut]:
    rows = session.scalars(select(Document).where(Document.consultation_id == consultation_id))
    return [record_service.document_to_out(d) for d in rows if _can_read(session, actor, d)]


def authorized_documents(session: Session, actor: Actor) -> list[tuple[PatientIdentity, DocumentOut]]:
    """Every document this doctor may see: across patients with an active consent here, within scope."""
    if actor.role != Role.DOCTOR:
        raise access_service.AccessDenied("Doctors only")
    out = []
    for entry in patient_service.with_access(session, actor):
        rows = session.scalars(select(Document).where(Document.patient_id == entry.patient.id)
                               .order_by(Document.created_at.desc()))
        visible = [record_service.document_to_out(d) for d in rows if entry.access.can(d.record_category)]
        if visible:
            audit_service.log_record_access(session, actor, entry.patient.id, "documents_list",
                                            entry.access.categories, entry.access.consent_id)
        out.extend((entry.patient, d) for d in visible)
    # Plus documents this doctor uploaded themselves.
    seen = {d.id for _, d in out}
    for d in session.scalars(select(Document).where(Document.uploaded_by == actor.id)):
        if d.id not in seen:
            out.append((PatientIdentity.model_validate(session.get(Patient, d.patient_id)), record_service.document_to_out(d)))
    return sorted(out, key=lambda t: t[1].created_at, reverse=True)
