"""Append-only writes to a patient's longitudinal timeline. Reads go through record_service."""

from datetime import datetime

from sqlalchemy.orm import Session

from core.models import SourceType, TimelineEvent, utcnow


def append_event(
    session: Session,
    *,
    patient_id: int,
    event_type: str,
    record_category: str,
    ref_table: str,
    ref_id: int,
    actor_id: int | None,
    organization_id: int | None,
    summary: str,
    source_type: str = SourceType.PROVIDER,
    occurred_at: datetime | None = None,
    patient_visible: bool = True,
) -> TimelineEvent:
    event = TimelineEvent(
        patient_id=patient_id, event_type=event_type, record_category=record_category,
        ref_table=ref_table, ref_id=ref_id, actor_id=actor_id, organization_id=organization_id,
        source_type=source_type, summary=summary, occurred_at=occurred_at or utcnow(), patient_visible=patient_visible,
    )
    session.add(event)
    return event
