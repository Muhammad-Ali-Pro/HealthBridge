"""Reads of AI-generated records (AIFlag, AISummary), scoped to patients the doctor may access.

Agents that produce these records arrive in Phase 5; clinician review actions in Phase 6.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import AIFlag, AISummary, FlagStatus, Role
from core.schemas import Actor, AIFlagOut, AISummaryOut
from services import patient_service


def _patient_ids(session: Session, actor: Actor) -> list[int]:
    if actor.role != Role.DOCTOR:
        return []
    return [e.patient.id for e in patient_service.with_access(session, actor)]


def list_flags(session: Session, actor: Actor, status: str | None = None) -> list[AIFlagOut]:
    stmt = select(AIFlag).where(AIFlag.patient_id.in_(_patient_ids(session, actor)))
    if status:
        stmt = stmt.where(AIFlag.status == status)
    out = []
    for f in session.scalars(stmt.order_by(AIFlag.created_at.desc())):
        item = AIFlagOut.model_validate(f)
        item.patient_name = f.patient.name
        out.append(item)
    return out


def list_summaries(session: Session, actor: Actor) -> list[AISummaryOut]:
    """Only summaries THIS doctor generated in THIS organization (each reflects that consent scope)."""
    rows = session.scalars(select(AISummary).where(
        AISummary.patient_id.in_(_patient_ids(session, actor)), AISummary.requested_by == actor.id,
        AISummary.organization_id == actor.organization_id).order_by(AISummary.generated_at.desc()))
    return [AISummaryOut.model_validate(s) for s in rows]


def review_counts(session: Session, actor: Actor) -> dict[str, int]:
    flags = list_flags(session, actor)
    return {s.value: sum(f.status == s for f in flags) for s in FlagStatus}
