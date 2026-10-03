"""Pharmacy view: ONLY prescriptions routed to the acting pharmacy (minimum necessary).

Exposed: patient identity + allergies (needed for a safe dispensing check), prescriber,
prescribing organization, items, dosage/instructions, status, and this pharmacy's own dispensing
and billing records. Not exposed: consultation reason, diagnoses, other providers' records or the
patient's timeline.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import Invoice, OrgType, Patient, PaymentStatus, Prescription, PrescriptionStatus, Role
from core.schemas import Actor, InvoiceOut, PatientIdentity, PrescriptionOut
from services import access_service, provider_service, record_service

AWAITING = [PrescriptionStatus.SENT]
READY = [PrescriptionStatus.VERIFIED, PrescriptionStatus.PARTIALLY_DISPENSED]
DONE = [PrescriptionStatus.DISPENSED]
HIDDEN = [PrescriptionStatus.DRAFT, PrescriptionStatus.ISSUED]  # not yet sent to a pharmacy


def _require_pharmacy(actor: Actor) -> int:
    if actor.role != Role.PHARMACIST or actor.organization is None or actor.organization.org_type != OrgType.PHARMACY:
        raise access_service.AccessDenied("Pharmacy staff only")
    return actor.organization.id


def list_prescriptions(session: Session, actor: Actor, statuses: list[str] | None = None) -> list[PrescriptionOut]:
    pharmacy_id = _require_pharmacy(actor)
    stmt = select(Prescription).where(Prescription.pharmacy_id == pharmacy_id, Prescription.status.notin_(HIDDEN))
    if statuses:
        stmt = stmt.where(Prescription.status.in_(statuses))
    rows = session.scalars(stmt.order_by(Prescription.created_at.desc()))
    return [record_service.prescription_to_out(rx, include_reason=False, include_invoice=True) for rx in rows]


def queue_overview(session: Session, actor: Actor) -> dict[str, int]:
    rxs = list_prescriptions(session, actor)
    today = provider_service.start_of_today()
    awaiting = sum(rx.status in AWAITING for rx in rxs)
    ready = sum(rx.status in READY for rx in rxs)
    return {
        "pending": awaiting + ready,
        "awaiting_verification": awaiting,
        "ready_to_dispense": ready,
        "dispensed_today": sum(rx.status in DONE and rx.dispensed_at is not None and rx.dispensed_at >= today
                               for rx in rxs),
        "dispensed_total": sum(rx.status in DONE for rx in rxs),
    }


def list_invoices(session: Session, actor: Actor) -> list[InvoiceOut]:
    pharmacy_id = _require_pharmacy(actor)
    rows = session.scalars(select(Invoice).where(Invoice.organization_id == pharmacy_id)
                           .order_by(Invoice.created_at.desc()))
    return [record_service.invoice_to_out(i) for i in rows]


def billing_overview(session: Session, actor: Actor) -> dict[str, float]:
    invoices = list_invoices(session, actor)
    return {
        "invoices": len(invoices),
        "billed": sum(i.total for i in invoices if i.payment_status != PaymentStatus.CANCELLED),
        "collected": sum(i.amount_paid for i in invoices),
        "outstanding": sum(i.total - i.amount_paid for i in invoices
                           if i.payment_status in (PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID)),
    }


def patients(session: Session, actor: Actor) -> list[tuple[PatientIdentity, list[PrescriptionOut]]]:
    """Patients with prescriptions at this pharmacy, with only those prescriptions."""
    grouped: dict[int, list[PrescriptionOut]] = {}
    for rx in list_prescriptions(session, actor):
        grouped.setdefault(rx.patient_id, []).append(rx)
    out = [(PatientIdentity.model_validate(session.get(Patient, pid)), rxs) for pid, rxs in grouped.items()]
    return sorted(out, key=lambda t: t[0].name)
