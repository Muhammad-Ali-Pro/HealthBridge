"""Audit log: every consent action and every consent-based record access is recorded."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import AuditAction, AuditLog, Organization, Patient, User, utcnow
from core.schemas import Actor, AuditEntryOut

# A provider re-opening the same view of the same record within this window is one access session.
ACCESS_DEDUPE_WINDOW = timedelta(minutes=15)


def log(
    session: Session,
    *,
    action: str,
    actor_id: int | None,
    actor_type: str,
    patient_id: int | None = None,
    provider_id: int | None = None,
    organization_id: int | None = None,
    resource_type: str = "",
    resource_id: int | None = None,
    details: dict | None = None,
    timestamp=None,
) -> AuditLog:
    entry = AuditLog(
        action=action, actor_id=actor_id, actor_type=actor_type, patient_id=patient_id,
        provider_id=provider_id, organization_id=organization_id, resource_type=resource_type,
        resource_id=resource_id, details=details or {}, timestamp=timestamp or utcnow(),
    )
    session.add(entry)
    session.flush()
    return entry


def log_record_access(session: Session, actor: Actor, patient_id: int, view: str, scope: list[str] | str,
                      consent_id: int | None) -> AuditLog | None:
    """RECORD_ACCESSED, de-duplicated so Streamlit reruns don't flood the log."""
    recent = session.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.RECORD_ACCESSED,
            AuditLog.actor_id == actor.id,
            AuditLog.patient_id == patient_id,
            AuditLog.organization_id == actor.organization_id,
            AuditLog.resource_type == view,
            AuditLog.timestamp >= utcnow() - ACCESS_DEDUPE_WINDOW,
        ).limit(1)
    )
    if recent:
        return None
    return log(
        session, action=AuditAction.RECORD_ACCESSED, actor_id=actor.id, actor_type=actor.role,
        patient_id=patient_id, provider_id=actor.id, organization_id=actor.organization_id,
        resource_type=view, details={"scope": scope, "consent_id": consent_id},
    )


def _to_out(session: Session, e: AuditLog) -> AuditEntryOut:
    def name(model, pk):
        row = session.get(model, pk) if pk else None
        return row.name if row else None

    return AuditEntryOut(
        id=e.id, action=e.action, actor_name=name(User, e.actor_id), actor_type=e.actor_type,
        patient_name=name(Patient, e.patient_id), provider_name=name(User, e.provider_id),
        organization_name=name(Organization, e.organization_id), resource_type=e.resource_type,
        resource_id=e.resource_id, details=e.details or {}, timestamp=e.timestamp,
    )


ACCESS_ACTIONS = [AuditAction.CONSENT_GRANTED, AuditAction.CONSENT_REVOKED,
                  AuditAction.RECORD_ACCESSED, AuditAction.ACCESS_DENIED, AuditAction.AI_SUMMARY_GENERATED]
ACTIVITY_ACTIONS = [AuditAction.RECORD_CREATED, AuditAction.RECORD_UPDATED]


def patient_history(session: Session, actor: Actor, patient_id: int, limit: int = 100,
                    include_activity: bool = False) -> list[AuditEntryOut]:
    """Consent/access history (and optionally record activity) for a patient — visible to that patient only."""
    from services import access_service  # local import: access_service depends on this module

    access_service.require_self(session, actor, patient_id)
    actions = ACCESS_ACTIONS + (ACTIVITY_ACTIONS if include_activity else [])
    rows = session.scalars(
        select(AuditLog).where(AuditLog.patient_id == patient_id, AuditLog.action.in_(actions))
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit)
    )
    # Private drafts and internal clinician notes are not part of the patient's view.
    def patient_may_see(e: AuditLog) -> bool:
        d = e.details or {}
        return "draft" not in str(d.get("event", "")) and d.get("patient_visible", True) is not False

    return [_to_out(session, e) for e in rows if patient_may_see(e)]


def provider_activity(session: Session, actor: Actor, limit: int = 20) -> list[AuditEntryOut]:
    """What this provider recently did (their own audit trail)."""
    rows = session.scalars(select(AuditLog).where(AuditLog.actor_id == actor.id)
                           .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit))
    return [_to_out(session, e) for e in rows]
