"""Laboratory view: ONLY test orders routed to the acting lab.

Exposed: patient identity, ordering provider + organization, test, priority, clinical notes
written for the lab, and the lab's own results. Not exposed: the patient's wider record.
Result entry / verification / publication arrive with the lab workflow phase.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import LabOrder, LabOrderStatus, OrgType, Role
from core.schemas import Actor, LabOrderOut, PatientIdentity
from services import access_service, provider_service, record_service

OPEN_ORDERS = [LabOrderStatus.ORDERED, LabOrderStatus.RECEIVED]
PENDING_REPORTS = [LabOrderStatus.RESULTED, LabOrderStatus.VERIFIED]


def _require_lab(actor: Actor) -> int:
    if actor.role != Role.LAB or actor.organization is None or actor.organization.org_type != OrgType.LABORATORY:
        raise access_service.AccessDenied("Laboratory staff only")
    return actor.organization.id


def list_orders(session: Session, actor: Actor, statuses: list[str] | None = None) -> list[LabOrderOut]:
    lab_id = _require_lab(actor)
    stmt = select(LabOrder).where(LabOrder.lab_id == lab_id)
    if statuses:
        stmt = stmt.where(LabOrder.status.in_(statuses))
    rows = session.scalars(stmt.order_by(LabOrder.ordered_at.desc()))
    return [record_service.lab_to_out(o, include_unpublished_results=True) for o in rows]


def overview(session: Session, actor: Actor) -> dict[str, int]:
    orders = list_orders(session, actor)
    today = provider_service.start_of_today()
    return {
        "new_orders": sum(o.status == LabOrderStatus.ORDERED for o in orders),
        "in_progress": sum(o.status == LabOrderStatus.RECEIVED for o in orders),
        "awaiting_verification": sum(o.status == LabOrderStatus.RESULTED for o in orders),
        "ready_to_publish": sum(o.status == LabOrderStatus.VERIFIED for o in orders),
        "published_today": sum(o.status == LabOrderStatus.PUBLISHED and o.published_at is not None
                               and o.published_at >= today for o in orders),
        "published_total": sum(o.status == LabOrderStatus.PUBLISHED for o in orders),
    }


def patients(session: Session, actor: Actor) -> list[tuple[PatientIdentity, list[LabOrderOut]]]:
    grouped: dict[int, list[LabOrderOut]] = {}
    for o in list_orders(session, actor):
        grouped.setdefault(o.patient.id, []).append(o)
    return sorted(((orders[0].patient, orders) for orders in grouped.values()), key=lambda t: t[0].name)
