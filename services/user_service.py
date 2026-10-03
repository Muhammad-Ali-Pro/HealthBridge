"""Demo identities, provider memberships and the acting context (no real authentication)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import Organization, ProviderOrganization, Role, User
from core.schemas import Actor, MembershipOut, OrganizationOut, UserOut


def list_users_by_role(session: Session, role: str) -> list[UserOut]:
    # Seed order puts the primary demo identities (Dr. Ayesha, Sana, Nadia, Ahmed) first.
    rows = session.scalars(select(User).where(User.role == role).order_by(User.id)).all()
    return [UserOut.model_validate(u) for u in rows]


def get_user(session: Session, user_id: int) -> UserOut | None:
    user = session.get(User, user_id)
    return UserOut.model_validate(user) if user else None


def memberships(session: Session, user_id: int) -> list[MembershipOut]:
    rows = session.scalars(
        select(ProviderOrganization)
        .where(ProviderOrganization.provider_id == user_id, ProviderOrganization.active.is_(True))
        .order_by(ProviderOrganization.is_primary.desc(), ProviderOrganization.id)
    )
    return [MembershipOut(organization=OrganizationOut.model_validate(m.organization), title=m.title,
                          is_primary=m.is_primary) for m in rows]


def make_actor(session: Session, user_id: int, organization_id: int | None = None) -> Actor:
    """Build the acting context. Staff act within one of their organizations (primary by default)."""
    user = UserOut.model_validate(session.get(User, user_id))
    if user.role == Role.PATIENT:
        return Actor(user=user)
    orgs = memberships(session, user_id)
    chosen = next((m for m in orgs if m.organization.id == organization_id), orgs[0] if orgs else None)
    return Actor(user=user, organization=chosen.organization if chosen else None)


def find_persona(session: Session, user_name: str, organization_name: str | None) -> tuple[int, int | None]:
    """Resolve a demo persona (by name) to (user_id, organization_id)."""
    user_id = session.scalar(select(User.id).where(User.name == user_name))
    org_id = (session.scalar(select(Organization.id).where(Organization.name == organization_name))
              if organization_name else None)
    return user_id, org_id


def list_organizations(session: Session, org_type: str | None = None) -> list[OrganizationOut]:
    stmt = select(Organization).order_by(Organization.name)
    if org_type:
        stmt = stmt.where(Organization.org_type == org_type)
    return [OrganizationOut.model_validate(o) for o in session.scalars(stmt)]


def get_organization(session: Session, organization_id: int) -> OrganizationOut:
    return OrganizationOut.model_validate(session.get(Organization, organization_id))
