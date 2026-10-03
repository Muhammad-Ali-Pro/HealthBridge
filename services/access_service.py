"""Access control for patient records — enforced here, never only in the UI.

A doctor may read a patient's record only when ALL of these hold:
  1. the actor is a doctor acting in a specific organization context,
  2. the patient has a consent for exactly that provider AND organization,
  3. the consent is not revoked,
  4. the consent has not expired (expires_at, or "one consultation" already used),
and then only the record categories the consent covers.

Patients always see their own full record. Pharmacies and laboratories never read the
longitudinal record; they only see prescriptions / test orders routed to their organization.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import (
    AuditAction,
    Consent,
    ConsentDuration,
    ConsentScopeType,
    ConsentStatus,
    Consultation,
    Patient,
    RecordCategory,
    Role,
    utcnow,
)
from core.schemas import AccessDecision, Actor
from services import audit_service

ALL_CATEGORIES = [c.value for c in RecordCategory]
# A "one consultation" consent stays usable this long after the consultation is recorded,
# so the doctor can finish the visit (prescribe, order tests).
ONE_CONSULTATION_GRACE = timedelta(hours=2)


class AccessDenied(PermissionError):
    pass


def effective_status(session: Session, consent: Consent) -> str:
    if consent.status == ConsentStatus.REVOKED or consent.revoked_at:
        return ConsentStatus.REVOKED
    now = utcnow()
    if consent.expires_at and consent.expires_at <= now:
        return ConsentStatus.EXPIRED
    if consent.duration == ConsentDuration.ONE_CONSULTATION:
        visit = session.scalar(
            select(Consultation.date).where(
                Consultation.patient_id == consent.patient_id,
                Consultation.provider_id == consent.provider_id,
                Consultation.organization_id == consent.organization_id,
                Consultation.date >= consent.granted_at,
            ).order_by(Consultation.date).limit(1)
        )
        if visit and visit + ONE_CONSULTATION_GRACE <= now:
            return ConsentStatus.EXPIRED
    return ConsentStatus.ACTIVE


def consent_categories(consent: Consent) -> list[str]:
    if consent.scope_type == ConsentScopeType.ALL:
        return list(ALL_CATEGORIES)
    return [s.record_category for s in consent.scopes if s.allowed]


def active_consent(session: Session, patient_id: int, provider_id: int, organization_id: int | None) -> Consent | None:
    if organization_id is None:
        return None
    candidates = session.scalars(
        select(Consent).where(
            Consent.patient_id == patient_id,
            Consent.provider_id == provider_id,
            Consent.organization_id == organization_id,
            Consent.status == ConsentStatus.ACTIVE,
        ).order_by(Consent.granted_at.desc())
    )
    return next((c for c in candidates if effective_status(session, c) == ConsentStatus.ACTIVE), None)


def authorize(session: Session, actor: Actor, patient_id: int) -> AccessDecision:
    """Decide (without logging) what `actor` may see of `patient_id`'s record."""
    base = dict(patient_id=patient_id)
    if session.get(Patient, patient_id) is None:
        return AccessDecision(allowed=False, via="none", reason="Unknown patient", **base)

    if actor.role == Role.PATIENT:
        own = session.scalar(select(Patient.id).where(Patient.user_id == actor.id))
        if own == patient_id:
            return AccessDecision(allowed=True, via="self", reason="Your own record",
                                  scope_type=ConsentScopeType.ALL, categories=list(ALL_CATEGORIES), **base)
        return AccessDecision(allowed=False, via="none", reason="Patients can only see their own record", **base)

    if actor.role != Role.DOCTOR:
        return AccessDecision(allowed=False, via="none", reason=(
            "Pharmacies and laboratories only see the prescriptions and test orders sent to them."), **base)

    if actor.organization_id is None:
        return AccessDecision(allowed=False, via="none", reason="Select the organization you are working at.", **base)

    consent = active_consent(session, patient_id, actor.id, actor.organization_id)
    if consent is None:
        return AccessDecision(allowed=False, via="none",
                              reason="Patient consent is required to access this patient's HealthBridge records.",
                              **base)
    return AccessDecision(allowed=True, via="consent", reason="Patient has granted you access",
                          consent_id=consent.id, scope_type=consent.scope_type,
                          categories=consent_categories(consent), **base)


def require(session: Session, actor: Actor, patient_id: int, category: str | None = None) -> AccessDecision:
    """authorize() or raise AccessDenied (and audit the denial)."""
    decision = authorize(session, actor, patient_id)
    if decision.allowed and (category is None or decision.can(category)):
        return decision
    audit_service.log(
        session, action=AuditAction.ACCESS_DENIED, actor_id=actor.id, actor_type=actor.role,
        patient_id=patient_id, provider_id=actor.id if actor.role == Role.DOCTOR else None,
        organization_id=actor.organization_id, resource_type=category or "record",
        details={"reason": decision.reason if not decision.allowed else f"'{category}' not in consent scope"},
    )
    raise AccessDenied(decision.reason if not decision.allowed else f"{category} is not shared with you")


def require_self(session: Session, actor: Actor, patient_id: int) -> None:
    decision = authorize(session, actor, patient_id)
    if decision.via != "self":
        raise AccessDenied("Only the patient can do this")
