"""One place to record that a clinical record was created/updated: timeline event + audit entry."""

from sqlalchemy.orm import Session

from core.models import AuditAction, SourceType, utcnow
from core.schemas import Actor
from services import audit_service, timeline_service


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
) -> None:
    """Timeline event (finalized records only) + audit entry carrying actor, organization and patient."""
    when = when or utcnow()
    if on_timeline:
        timeline_service.append_event(
            session, patient_id=patient_id, event_type=event, record_category=category, ref_table=resource_type,
            ref_id=resource_id, actor_id=actor.id, organization_id=actor.organization_id, summary=summary,
            source_type=SourceType.PROVIDER, occurred_at=when)
    audit_service.log(
        session, action=action, actor_id=actor.id, actor_type=actor.role, patient_id=patient_id,
        provider_id=actor.id, organization_id=actor.organization_id, resource_type=resource_type,
        resource_id=resource_id, timestamp=when,
        # Summaries of drafts are not stored: drafts are private until finalized.
        details={"event": event, "summary": summary if on_timeline else ""},
    )
