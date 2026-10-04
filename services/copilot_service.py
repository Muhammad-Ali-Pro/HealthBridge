"""AI Clinical Copilot service: consent first, AI second.

    Doctor → consent / authorization (access_service.require) → Record Retrieval Agent (consent-bound handle)
           → Clinical Summary Agent → Safety / Consistency Agent → stored for doctor review

* The agents never receive a database session. The Record Retrieval Agent gets a `_ScopedRecordSource`
  bound to one doctor + organization + patient, which re-checks consent on every fetch.
* Each Safety / Consistency flag is stored as an AIFlag scoped to the requesting doctor and organization,
  so the doctor can Accept / Dismiss it. AI never modifies clinical records.
* "View source" resolves cited record ids by re-reading the record through the consent service.
* The AI provider (e.g. Gemini with the tester's own key) is passed in by the caller. This service never
  stores, logs or audits API keys; audit entries never contain prompts or record content.
* Without a live provider the agents return a deterministic demo response, labelled as such (generator
  "rule_based") — it is never presented as live model output.
"""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import copilot, organizer
from agents.organizer import record_counts, retrieval_counts
from agents.providers import AIProvider
from agents.schemas import CopilotResult
from core.models import AIFlag, AISummary, AuditAction, FlagStatus, Patient, Role, User, utcnow
from core.schemas import Actor, AIFlagOut, AuthorizedRecord, SourceDetail
from services import access_service, audit_service, record_service

SEVERITY_TO_FLAG = {"high": "high", "medium": "warning", "low": "info"}


class _ScopedRecordSource:
    """Consent-bound, single-patient record handle given to the Record Retrieval Agent.

    It exposes only `fetch()`; the session and actor are private and every fetch goes through the
    consent service, so the agent can never read unrestricted data.
    """

    def __init__(self, session: Session, actor: Actor, patient_id: int):
        self.__session, self.__actor = session, actor
        self.patient_id, self.provider_id, self.organization_id = patient_id, actor.id, actor.organization_id

    def fetch(self) -> AuthorizedRecord:
        return record_service.get_authorized_record(self.__session, self.__actor, self.patient_id, view="ai_copilot")


def _require_doctor(session: Session, actor: Actor, patient_id: int):
    if actor.role != Role.DOCTOR or actor.organization_id is None:
        raise access_service.AccessDenied("The AI Clinical Copilot is available to doctors at an organization")
    return access_service.require(session, actor, patient_id)


def preview(session: Session, actor: Actor, patient_id: int) -> dict[str, int]:
    """How many consented records the agents would analyse right now (shown before generating)."""
    _require_doctor(session, actor, patient_id)
    dataset, _ = organizer.organize(_ScopedRecordSource(session, actor, patient_id).fetch())
    return retrieval_counts(dataset)


def generate(session: Session, actor: Actor, patient_id: int, *,
             provider: AIProvider | None = None,
             on_progress: Callable[[str], None] | None = None) -> CopilotResult:
    # 1. Consent / authorization — without an active consent here, no agent runs at all.
    _require_doctor(session, actor, patient_id)
    # 2–4. Multi-agent graph over a consent-bound handle.
    state = copilot.run(_ScopedRecordSource(session, actor, patient_id), provider, on_progress)
    live = state["generator"] == "llm"
    now = utcnow()
    summary_row = AISummary(patient_id=patient_id, content="AI Clinical Copilot summary", generated_at=now,
                            generator=state["generator"], requested_by=actor.id, organization_id=actor.organization_id)
    session.add(summary_row)
    session.flush()

    # 5. Store each flag for clinician review (AI may write AIFlag/AISummary only).
    items = []
    for item in state["summary"].items_for_review:
        flag = AIFlag(patient_id=patient_id, severity=SEVERITY_TO_FLAG[item.severity], category=item.category,
                      message=item.issue, evidence={"reason": item.evidence, "recommendation": item.recommendation},
                      sources=item.sources, status=FlagStatus.OPEN, created_at=now, summary_id=summary_row.id,
                      requested_by=actor.id, organization_id=actor.organization_id)
        session.add(flag)
        session.flush()
        items.append(item.model_copy(update={"flag_id": flag.id}))

    result = CopilotResult(
        patient_name=_patient_name(session, patient_id),
        patient_display_id=f"HB-{patient_id:06d}", provider_name=actor.user.name,
        organization_name=actor.organization.name, authorized_categories=state["categories"],
        summary=state["summary"].model_copy(update={"items_for_review": items}), sources=state["sources"],
        generator=state["generator"], provider=provider.label if live else None,
        model=provider.get_model_name() if live else None,
        notices=state.get("notices", []), removed_unsupported=state.get("removed", 0),
        record_counts=record_counts(state["dataset"]), retrieval=state["retrieval"], summary_id=summary_row.id,
        generated_at=now,
    )
    summary_row.payload = result.model_dump(mode="json")
    audit_service.log(
        session, action=AuditAction.AI_SUMMARY_GENERATED, actor_id=actor.id, actor_type=actor.role,
        patient_id=patient_id, provider_id=actor.id, organization_id=actor.organization_id,
        resource_type="ai_summary", resource_id=summary_row.id, timestamp=now,
        # No prompts or record content — only what was produced and from which scope.
        details={"generator": result.generator, "model": result.model, "scope": result.authorized_categories,
                 "record_counts": result.record_counts, "items_for_review": len(items)},
    )
    session.flush()
    return result


def _patient_name(session: Session, patient_id: int) -> str:
    return session.get(Patient, patient_id).name


def latest(session: Session, actor: Actor, patient_id: int) -> CopilotResult | None:
    """This doctor's most recent summary here — only while their consent is still active."""
    if actor.role != Role.DOCTOR:
        return None
    access_service.require(session, actor, patient_id)
    row = session.scalar(select(AISummary).where(
        AISummary.patient_id == patient_id, AISummary.requested_by == actor.id,
        AISummary.organization_id == actor.organization_id).order_by(AISummary.generated_at.desc()).limit(1))
    return CopilotResult.model_validate(row.payload) if row and row.payload else None


# ---------------------------------------------------------------------------
# Flags: accept / dismiss / view source
# ---------------------------------------------------------------------------


def _flag_out(session: Session, f: AIFlag) -> AIFlagOut:
    out = AIFlagOut.model_validate(f)
    out.patient_name = f.patient.name
    out.reviewed_by_name = session.get(User, f.reviewed_by).name if f.reviewed_by else None
    return out


def _own_flag(session: Session, actor: Actor, flag_id: int) -> AIFlag:
    f = session.get(AIFlag, flag_id)
    if f is None or f.requested_by != actor.id or f.organization_id != actor.organization_id:
        raise access_service.AccessDenied("This AI flag belongs to another clinician or organization context")
    access_service.require(session, actor, f.patient_id)  # consent must still be active
    return f


def flags_for_summary(session: Session, actor: Actor, summary_id: int) -> dict[int, AIFlagOut]:
    rows = session.scalars(select(AIFlag).where(AIFlag.summary_id == summary_id, AIFlag.requested_by == actor.id,
                                                AIFlag.organization_id == actor.organization_id))
    flags = list(rows)
    if flags:
        access_service.require(session, actor, flags[0].patient_id)
    return {f.id: _flag_out(session, f) for f in flags}


def review_flag(session: Session, actor: Actor, flag_id: int, decision: str, note: str = "") -> AIFlagOut:
    """Doctor's decision on a flag: accepted or dismissed. Never changes any clinical record."""
    decision = FlagStatus(decision)
    if decision == FlagStatus.OPEN:
        raise ValueError("Choose accept or dismiss")
    f = _own_flag(session, actor, flag_id)
    f.status, f.reviewed_by, f.reviewed_at, f.review_note = decision, actor.id, utcnow(), (note or "").strip()
    session.flush()
    audit_service.log(session, action=AuditAction.AI_FLAG_REVIEWED, actor_id=actor.id, actor_type=actor.role,
                      patient_id=f.patient_id, provider_id=actor.id, organization_id=actor.organization_id,
                      resource_type="ai_flag", resource_id=f.id, details={"decision": decision, "category": f.category})
    return _flag_out(session, f)


def resolve_sources(session: Session, actor: Actor, patient_id: int, source_ids: list[str]) -> list[SourceDetail]:
    """'View source': re-read each cited record THROUGH the consent service and describe it."""
    _require_doctor(session, actor, patient_id)
    record = record_service.get_authorized_record(session, actor, patient_id, view="ai_source")
    return [_describe(record, sid) for sid in source_ids]


def _describe(record: AuthorizedRecord, sid: str) -> SourceDetail:
    p = record.patient
    if sid == "PROFILE":
        return SourceDetail(id=sid, record_type="Patient profile", date=None, organization_name=None,
                            organization_type=None, provider_name=None, title="Clinician-documented profile",
                            excerpt=f"Allergies: {', '.join(p.allergies) or 'none'} · Conditions: "
                                    f"{', '.join(p.conditions) if p.conditions is not None else 'not shared'}")
    for c in record.consultations:
        if sid == f"C-{c.id}":
            return SourceDetail(id=sid, record_type="Consultation", date=c.date, organization_name=c.organization_name,
                                organization_type=c.organization_type, provider_name=c.provider_name, title=c.complaint,
                                excerpt=" · ".join(x for x in (c.assessment, c.diagnosis, c.treatment_plan) if x))
    for n in record.notes:
        if sid == f"N-{n.id}":
            return SourceDetail(id=sid, record_type=f"Clinical note ({n.note_type.replace('_', ' ')})", date=n.created_at,
                                organization_name=n.organization_name, organization_type=n.organization_type,
                                provider_name=n.provider_name, title="Clinical note", excerpt=n.content)
    for rx in record.prescriptions:
        if sid == rx.display_id:
            return SourceDetail(id=sid, record_type="Prescription", date=rx.created_at,
                                organization_name=rx.organization_name, organization_type=rx.organization_type,
                                provider_name=rx.provider_name, title=f"{rx.display_id} · {rx.status.replace('_', ' ')}",
                                excerpt="; ".join(f"{i.drug_name} {i.strength} {i.dosage} {i.frequency}, {i.duration_days} days"
                                                  for i in rx.items))
    for m in record.medications:
        if sid == f"RX-{m.prescription_id:05d}":
            return SourceDetail(id=sid, record_type="Current medication", date=m.started,
                                organization_name=m.organization_name, organization_type=None,
                                provider_name=m.prescribed_by, title=m.drug_name,
                                excerpt=f"{m.drug_name} {m.strength} {m.dosage} {m.frequency}")
    for o in record.reports:
        if sid == o.display_id:
            return SourceDetail(id=sid, record_type="Lab report", date=o.published_at or o.ordered_at,
                                organization_name=o.lab_name, organization_type="laboratory",
                                provider_name=o.provider_name, title=o.test_name,
                                excerpt="; ".join(f"{v.analyte} {v.value} {v.unit}" for v in o.values))
    for d in record.documents:
        if sid == f"DOC-{d.id}":
            return SourceDetail(id=sid, record_type="Document", date=d.created_at, organization_name=d.organization_name,
                                organization_type=d.organization_type, provider_name=d.uploaded_by_name, title=d.title,
                                excerpt=d.source)
    for e in record.patient_entries:
        if sid == f"PE-{e.id}":
            return SourceDetail(id=sid, record_type=f"Patient-provided {e.entry_type}", date=e.created_at,
                                organization_name=None, organization_type=None, provider_name="Patient",
                                title=e.title, excerpt=e.details)
    return SourceDetail(id=sid, record_type="Unavailable", date=None, organization_name=None, organization_type=None,
                        provider_name=None, title="Not available under your current consent",
                        excerpt="This record is not part of the records you are currently authorized to see.",
                        available=False)
