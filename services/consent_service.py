"""Patient-controlled consent: grant (selected categories or all records), revoke, list.

Consent never deletes or changes clinical records — it only controls access.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import (
    AuditAction,
    Consent,
    ConsentDuration,
    ConsentScope,
    ConsentScopeType,
    ConsentStatus,
    Organization,
    OrgType,
    Patient,
    ProviderOrganization,
    RecordCategory,
    Role,
    User,
    utcnow,
)
from core.schemas import Actor, ConsentOut, ProviderOption
from services import access_service, audit_service

DURATION_DELTA = {
    ConsentDuration.HOURS_24: timedelta(hours=24),
    ConsentDuration.DAYS_7: timedelta(days=7),
    # Safety cap: an unused "one consultation" consent lapses after 24 hours.
    ConsentDuration.ONE_CONSULTATION: timedelta(hours=24),
    ConsentDuration.UNTIL_REVOKED: None,
}


class ConsentError(ValueError):
    pass


def to_out(session: Session, c: Consent) -> ConsentOut:
    return ConsentOut(
        id=c.id, patient_id=c.patient_id, patient_name=c.patient.name,
        provider_id=c.provider_id, provider_name=c.provider.name,
        organization_id=c.organization_id, organization_name=c.organization.name,
        organization_type=c.organization.org_type,
        status=access_service.effective_status(session, c), scope_type=c.scope_type,
        categories=access_service.consent_categories(c), duration=c.duration,
        granted_at=c.granted_at, revoked_at=c.revoked_at, expires_at=c.expires_at, purpose=c.purpose,
    )


def _patient_for(session: Session, actor: Actor) -> Patient:
    patient = session.scalar(select(Patient).where(Patient.user_id == actor.id))
    if actor.role != Role.PATIENT or patient is None:
        raise access_service.AccessDenied("Only patients can manage consent for their own record")
    return patient


def search_providers(session: Session, query: str = "") -> list[ProviderOption]:
    """Doctor + organization pairs a patient can share with (e.g. 'Dr. Arif · South City Hospital')."""
    stmt = (
        select(ProviderOrganization)
        .join(User, User.id == ProviderOrganization.provider_id)
        .join(Organization, Organization.id == ProviderOrganization.organization_id)
        .where(User.role == Role.DOCTOR, ProviderOrganization.active.is_(True),
               Organization.org_type.in_([OrgType.CLINIC, OrgType.HOSPITAL]))
        # Each doctor's primary organization first (e.g. Dr. Arif → South City Hospital), then their others.
        .order_by(User.name, ProviderOrganization.is_primary.desc(), Organization.name)
    )
    if query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(User.name.ilike(q) | Organization.name.ilike(q))
    return [
        ProviderOption(
            provider_id=m.provider_id, provider_name=m.provider.name, specialty=m.provider.specialty,
            organization_id=m.organization_id, organization_name=m.organization.name,
            organization_type=m.organization.org_type,
        )
        for m in session.scalars(stmt)
    ]


def grant(
    session: Session,
    actor: Actor,
    *,
    provider_id: int,
    organization_id: int,
    scope_type: str,
    categories: list[str] | None = None,
    duration: str = ConsentDuration.UNTIL_REVOKED,
    purpose: str = "",
    confirm_all: bool = False,
) -> ConsentOut:
    """Patient grants a specific provider, in a specific organization, access to their record."""
    patient = _patient_for(session, actor)

    membership = session.scalar(select(ProviderOrganization).where(
        ProviderOrganization.provider_id == provider_id,
        ProviderOrganization.organization_id == organization_id,
        ProviderOrganization.active.is_(True),
    ))
    if membership is None or membership.provider.role != Role.DOCTOR:
        raise ConsentError("That doctor does not work at the selected organization")

    scope_type = ConsentScopeType(scope_type)
    duration = ConsentDuration(duration)
    if scope_type == ConsentScopeType.ALL and not confirm_all:
        raise ConsentError("Sharing all records requires explicit confirmation")
    selected = sorted({RecordCategory(c).value for c in (categories or [])})
    if scope_type == ConsentScopeType.SELECTED and not selected:
        raise ConsentError("Choose at least one type of record to share")

    now = utcnow()
    # One active consent per patient + provider + organization: a new grant supersedes the old one.
    previous = access_service.active_consent(session, patient.id, provider_id, organization_id)
    if previous:
        _revoke(session, actor, previous, reason="superseded by a new consent")

    delta = DURATION_DELTA[duration]
    consent = Consent(
        patient_id=patient.id, provider_id=provider_id, organization_id=organization_id,
        status=ConsentStatus.ACTIVE, scope_type=scope_type, duration=duration, granted_at=now,
        expires_at=now + delta if delta else None, purpose=purpose.strip(), created_by=actor.id,
        scopes=[ConsentScope(record_category=c, allowed=True) for c in
                (selected if scope_type == ConsentScopeType.SELECTED else [])],
    )
    session.add(consent)
    session.flush()

    audit_service.log(
        session, action=AuditAction.CONSENT_GRANTED, actor_id=actor.id, actor_type=actor.role,
        patient_id=patient.id, provider_id=provider_id, organization_id=organization_id,
        resource_type="consent", resource_id=consent.id, timestamp=now,
        details={"consent_id": f"CON-{consent.id:06d}", "scope_type": scope_type,
                 "all_records": scope_type == ConsentScopeType.ALL,
                 "categories": access_service.consent_categories(consent),
                 "duration": duration, "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
                 "purpose": consent.purpose},
    )
    return to_out(session, consent)


def _revoke(session: Session, actor: Actor, consent: Consent, reason: str = "") -> None:
    now = utcnow()
    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = now
    session.flush()
    audit_service.log(
        session, action=AuditAction.CONSENT_REVOKED, actor_id=actor.id, actor_type=actor.role,
        patient_id=consent.patient_id, provider_id=consent.provider_id,
        organization_id=consent.organization_id, resource_type="consent", resource_id=consent.id,
        timestamp=now, details={"consent_id": f"CON-{consent.id:06d}", "reason": reason,
                                "scope_type": consent.scope_type,
                                "categories": access_service.consent_categories(consent)},
    )


def revoke(session: Session, actor: Actor, consent_id: int) -> ConsentOut:
    """Patient revokes a consent. Records are untouched; the provider simply loses access."""
    patient = _patient_for(session, actor)
    consent = session.get(Consent, consent_id)
    if consent is None or consent.patient_id != patient.id:
        raise access_service.AccessDenied("You can only revoke consents on your own record")
    if consent.status != ConsentStatus.REVOKED:
        _revoke(session, actor, consent, reason="revoked by patient")
    return to_out(session, consent)


def list_for_patient(session: Session, actor: Actor) -> list[ConsentOut]:
    patient = _patient_for(session, actor)
    rows = session.scalars(select(Consent).where(Consent.patient_id == patient.id)
                           .order_by(Consent.granted_at.desc()))
    return [to_out(session, c) for c in rows]


def get_for_patient(session: Session, actor: Actor, consent_id: int) -> ConsentOut:
    patient = _patient_for(session, actor)
    consent = session.get(Consent, consent_id)
    if consent is None or consent.patient_id != patient.id:
        raise access_service.AccessDenied("Not your consent")
    return to_out(session, consent)
