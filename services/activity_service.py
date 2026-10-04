"""One place to record that a clinical record was created/updated: timeline event + audit entry."""

from sqlalchemy.orm import Session

from core.models import AuditAction, Role, SourceType, utcnow
from core.schemas import Actor
from services import audit_service, timeline_service


def source_for(actor: Actor) -> str:
    """Who contributed the record: the patient, a clinician (provider) or a pharmacy/laboratory (organization)."""
    if actor.role == Role.PATIENT:
        return SourceType.PATIENT
    if actor.role == Role.DOCTOR:
        return SourceType.PROVIDER
    return SourceType.ORGANIZATION


def record(
    session: Session,
    actor: Actor,
    *,
    patient_id: int,
    event: str,
    resource_type: str,
    resource_id: int,
    summary: str = "",
    category: str | None = None,
    on_timeline: bool = True,
    action: str = AuditAction.RECORD_CREATED,
    when=None,
    patient_visible: bool = True,
    source_type: str | None = None,
    organization_id: int | None | str = "actor",
    details: dict | None = None,
) -> None:
    """Timeline event (finalized records only) + audit entry carrying actor, organization, patient and source.

    * `source_type` defaults from the actor's role (patient / provider / organization).
    * `provider_id` on the audit row is set only when the actor is a doctor.
    * `organization_id` defaults to the actor's working organization (None for patients); pass it explicitly
      when the record concerns another organization (e.g. a patient sending a prescription to a pharmacy).
    * `details` adds non-sensitive metadata to the audit row.
    """
    when = when or utcnow()
    source = source_type or source_for(actor)
    org_id = actor.organization_id if organization_id == "actor" else organization_id
    if on_timeline:
        timeline_service.append_event(
            session, patient_id=patient_id, event_type=event, record_category=category, ref_table=resource_type,
            ref_id=resource_id, actor_id=actor.id, organization_id=org_id, summary=summary,
            source_type=source, occurred_at=when, patient_visible=patient_visible)
    audit_service.log(
        session, action=action, actor_id=actor.id, actor_type=actor.role, patient_id=patient_id,
        provider_id=actor.id if actor.role == Role.DOCTOR else None, organization_id=org_id,
        resource_type=resource_type, resource_id=resource_id, timestamp=when,
        # Drafts and internal notes keep no content here: they are not part of the patient's view.
        details={"event": event, "summary": summary if (on_timeline and patient_visible) else "",
                 "patient_visible": patient_visible and on_timeline, "source": source, **(details or {})},
    )
