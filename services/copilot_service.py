"""Clinical Copilot service: consent first, AI second.

    Patient database → consent service → authorized record retrieval → AI preparation → AI agents

The graph only ever receives `AuthorizedRecord` produced by record_service for THIS doctor in THIS
organization context. The output is stored as an AISummary (scoped to requester + organization) and the
generation is audited — without storing prompts.
"""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import copilot, llm as llm_module
from agents.organizer import record_counts
from agents.schemas import CopilotResult
from core.models import AISummary, AuditAction, Role, utcnow
from core.schemas import Actor
from services import access_service, audit_service, record_service


def _default_llm():
    return llm_module.complete_json if llm_module.available() else None


def generate(session: Session, actor: Actor, patient_id: int, *,
             llm: copilot.LLMFn | None | str = "default",
             on_progress: Callable[[str], None] | None = None) -> CopilotResult:
    if actor.role != Role.DOCTOR:
        raise access_service.AccessDenied("The Clinical Copilot is available to doctors")
    progress = on_progress or (lambda _m: None)
    progress("Reviewing authorized records…")
    # Consent check + filtering happen HERE, before any AI step (raises AccessDenied without consent).
    record = record_service.get_authorized_record(session, actor, patient_id, view="ai_copilot")

    state = copilot.run(record, _default_llm() if llm == "default" else llm, progress)
    now = utcnow()
    result = CopilotResult(
        patient_name=record.patient.name, patient_display_id=record.patient.display_id,
        provider_name=actor.user.name, organization_name=actor.organization.name,
        authorized_categories=record.access.categories, summary=state["summary"], sources=state["sources"],
        generator=state["generator"], notices=state.get("notices", []), removed_unsupported=state.get("removed", 0),
        record_counts=record_counts(state["dataset"]), generated_at=now,
    )
    row = AISummary(patient_id=patient_id, content=f"Clinical summary ({result.generator})", generated_at=now,
                    generator=result.generator, requested_by=actor.id, organization_id=actor.organization_id,
                    payload=result.model_dump(mode="json"))
    session.add(row)
    session.flush()
    audit_service.log(
        session, action=AuditAction.AI_SUMMARY_GENERATED, actor_id=actor.id, actor_type=actor.role,
        patient_id=patient_id, provider_id=actor.id, organization_id=actor.organization_id,
        resource_type="ai_summary", resource_id=row.id, timestamp=now,
        # No prompts or record content — only what was produced and from which scope.
        details={"generator": result.generator, "scope": record.access.categories,
                 "record_counts": result.record_counts, "items_for_review": len(result.summary.items_for_review)},
    )
    return result


def latest(session: Session, actor: Actor, patient_id: int) -> CopilotResult | None:
    """This doctor's most recent summary here — only while their consent is still active."""
    if actor.role != Role.DOCTOR:
        return None
    access_service.require(session, actor, patient_id)
    row = session.scalar(select(AISummary).where(
        AISummary.patient_id == patient_id, AISummary.requested_by == actor.id,
        AISummary.organization_id == actor.organization_id).order_by(AISummary.generated_at.desc()).limit(1))
    return CopilotResult.model_validate(row.payload) if row and row.payload else None
