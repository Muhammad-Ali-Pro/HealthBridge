"""Patient directory for providers: identity only, plus the viewer's access status.

Finding a patient never reveals clinical data — that requires record_service + consent.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Patient, Role
from core.schemas import Actor, DirectoryEntry, PatientIdentity
from services import access_service


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _search(session: Session, query: str | None):
    """Match by name, HealthBridge ID (HB-000001 / 1) or phone number (any formatting)."""
    stmt = select(Patient).order_by(Patient.name)
    q = (query or "").strip()
    if not q:
        return session.scalars(stmt)
    cond = Patient.name.ilike(f"%{q}%")
    upper = q.upper().replace(" ", "")
    if upper.startswith("HB"):
        hb = _digits(upper)
        if hb:
            cond = cond | (Patient.id == int(hb))
    elif _digits(q):
        digits = _digits(q)
        if len(digits) <= 6 and digits == q.strip():
            cond = cond | (Patient.id == int(digits))
        if len(digits) >= 4:
            normalized = func.replace(func.replace(func.replace(func.coalesce(Patient.phone, ""), "-", ""), " ", ""), "+", "")
            cond = cond | normalized.contains(digits)
    return session.scalars(stmt.where(cond))


def directory(session: Session, actor: Actor, query: str | None = None) -> list[DirectoryEntry]:
    """Doctors can find any patient by name/ID, but only see records where consent exists."""
    if actor.role != Role.DOCTOR:
        raise access_service.AccessDenied("Patient directory is for doctors")
    return [DirectoryEntry(patient=PatientIdentity.model_validate(p), access=access_service.authorize(session, actor, p.id))
            for p in _search(session, query)]


def with_access(session: Session, actor: Actor) -> list[DirectoryEntry]:
    """Patients who have granted this doctor access in the current organization."""
    return [e for e in directory(session, actor) if e.access.allowed]


def own_identity(session: Session, actor: Actor) -> PatientIdentity | None:
    patient = session.scalar(select(Patient).where(Patient.user_id == actor.id))
    return PatientIdentity.model_validate(patient) if patient else None
