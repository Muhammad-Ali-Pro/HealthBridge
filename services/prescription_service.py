"""Doctor e-prescriptions: DRAFT → ISSUED → SENT to a pharmacy (verification/dispensing is Phase 3).

* A prescription can hold several medicines.
* Organization context comes from the acting context.
* Issuing validates every medicine, stamps issued_at, writes a timeline event and an audit entry.
* Allergy warnings are deterministic catalog checks for the clinician — never automatic changes.
"""

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import (
    AuditAction,
    Consultation,
    ConsultationStatus,
    EventType,
    Organization,
    OrgType,
    Patient,
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
    RecordCategory,
    Role,
    utcnow,
)
from core.schemas import Actor, OrganizationOut, PrescriptionOut
from data.catalog import load_drug_catalog
from services import access_service, activity_service, record_service
from services.clinical_service import ClinicalValidationError

ROUTES = ["oral", "inhaled", "sublingual", "topical", "intravenous", "intramuscular", "subcutaneous", "rectal", "other"]


class MedicineInput(BaseModel):
    drug_name: str = ""
    strength: str = ""
    dosage: str = ""
    route: str = "oral"
    frequency: str = ""
    duration_days: int = Field(default=0, ge=0)
    quantity: int = Field(default=0, ge=0)
    instructions: str = ""


def validate_items(items: list[MedicineInput]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not items:
        errors["items"] = "Add at least one medicine."
    for i, m in enumerate(items):
        if not m.drug_name.strip():
            errors[f"{i}.drug_name"] = "Medicine name is required."
        if not m.strength.strip():
            errors[f"{i}.strength"] = "Strength is required."
        if not m.frequency.strip():
            errors[f"{i}.frequency"] = "Frequency is required."
        if m.duration_days <= 0:
            errors[f"{i}.duration_days"] = "Duration must be at least 1 day."
        if m.quantity <= 0:
            errors[f"{i}.quantity"] = "Quantity must be at least 1."
    return errors


def allergy_warnings(allergies: list[str], items: list[MedicineInput]) -> list[str]:
    """Catalog-based cross-check: documented allergy vs the medicine's allergy group. For clinician review."""
    catalog = {d["name"].lower(): d for d in load_drug_catalog()}
    found = []
    for m in items:
        drug = catalog.get(m.drug_name.strip().lower())
        group = (drug or {}).get("allergy_group")
        if not group:
            continue
        for allergy in allergies:
            a = allergy.lower()
            if group in a or a.rstrip("s") in group:
                found.append(f"{m.drug_name} belongs to the {group} group — patient has a documented "
                             f"{allergy} allergy. Verify before issuing.")
    return found


def _require_doctor_access(session: Session, actor: Actor, patient_id: int):
    if actor.role != Role.DOCTOR or actor.organization_id is None:
        raise access_service.AccessDenied("Only doctors working at an organization can prescribe")
    return access_service.require(session, actor, patient_id)


def _own_draft(session: Session, actor: Actor, prescription_id: int) -> Prescription:
    rx = session.get(Prescription, prescription_id)
    if rx is None or rx.provider_id != actor.id or rx.organization_id != actor.organization_id:
        raise access_service.AccessDenied("You can only change your own draft prescriptions at this organization")
    if rx.status != PrescriptionStatus.DRAFT:
        raise ClinicalValidationError({"status": "Only draft prescriptions can be changed."})
    return rx


def _label(items) -> str:
    return ", ".join(f"{i.drug_name} {i.strength}" for i in items)


def save_draft(session: Session, actor: Actor, patient_id: int, items: list[MedicineInput], *, notes: str = "",
               consultation_id: int | None = None, prescription_id: int | None = None) -> PrescriptionOut:
    _require_doctor_access(session, actor, patient_id)
    if consultation_id:
        c = session.get(Consultation, consultation_id)
        if c is None or c.patient_id != patient_id or c.status != ConsultationStatus.FINAL:
            raise ClinicalValidationError({"consultation": "Link the prescription to a finalized consultation."})
    if prescription_id:
        rx = _own_draft(session, actor, prescription_id)
        if rx.patient_id != patient_id:
            raise access_service.AccessDenied("Draft belongs to another patient")
        rx.items.clear()
        session.flush()
    else:
        rx = Prescription(patient_id=patient_id, provider_id=actor.id, organization_id=actor.organization_id,
                          status=PrescriptionStatus.DRAFT, created_at=utcnow())
        session.add(rx)
    rx.consultation_id = consultation_id
    rx.notes = (notes or "").strip()
    rx.items.extend(PrescriptionItem(**m.model_dump(exclude={"drug_name"}), drug_name=m.drug_name.strip())
                    for m in items if m.drug_name.strip())
    session.flush()
    activity_service.record(session, actor, patient_id=patient_id, event="prescription_draft_saved",
                            resource_type="prescriptions", resource_id=rx.id, on_timeline=False,
                            action=AuditAction.RECORD_UPDATED if prescription_id else AuditAction.RECORD_CREATED)
    return record_service.prescription_to_out(rx)


def issue(session: Session, actor: Actor, prescription_id: int) -> PrescriptionOut:
    rx = _own_draft(session, actor, prescription_id)
    _require_doctor_access(session, actor, rx.patient_id)
    items = [MedicineInput(**{k: getattr(i, k) for k in MedicineInput.model_fields}) for i in rx.items]
    errors = validate_items(items)
    if errors:
        raise ClinicalValidationError(errors)
    now = utcnow()
    rx.status = PrescriptionStatus.ISSUED
    rx.issued_at = now
    session.flush()
    activity_service.record(session, actor, patient_id=rx.patient_id, event=EventType.PRESCRIPTION_ISSUED,
                            category=RecordCategory.PRESCRIPTIONS, resource_type="prescriptions", resource_id=rx.id,
                            summary=f"{_label(rx.items)} prescribed · issued", when=now)
    return record_service.prescription_to_out(rx)


def available_pharmacies(session: Session) -> list[OrganizationOut]:
    """Demo pharmacies a prescription can be sent to."""
    rows = session.scalars(select(Organization).where(Organization.org_type == OrgType.PHARMACY)
                           .order_by(Organization.name))
    return [OrganizationOut.model_validate(o) for o in rows]


def send_to_pharmacy(session: Session, actor: Actor, prescription_id: int, pharmacy_id: int) -> PrescriptionOut:
    """Hand an ISSUED prescription to a pharmacy → SENT. The pharmacy's own workflow is Phase 3.

    Only the prescribing doctor, in the organization where it was written, can send it — and only while
    the patient's consent for that doctor here is still active.
    """
    rx = session.get(Prescription, prescription_id)
    if rx is None or rx.provider_id != actor.id or rx.organization_id != actor.organization_id:
        raise access_service.AccessDenied("Only the prescribing doctor at this organization can send this prescription")
    _require_doctor_access(session, actor, rx.patient_id)
    if rx.status != PrescriptionStatus.ISSUED:
        raise ClinicalValidationError({"status": "Only an issued prescription that has not been sent can be sent "
                                                 "to a pharmacy."})
    pharmacy = session.get(Organization, pharmacy_id)
    if pharmacy is None or pharmacy.org_type != OrgType.PHARMACY:
        raise ClinicalValidationError({"pharmacy": "Choose a pharmacy."})
    now = utcnow()
    rx.pharmacy, rx.status, rx.sent_at = pharmacy, PrescriptionStatus.SENT, now
    session.flush()
    activity_service.record(session, actor, patient_id=rx.patient_id, event=EventType.PRESCRIPTION_SENT,
                            category=RecordCategory.PRESCRIPTIONS, resource_type="prescriptions", resource_id=rx.id,
                            summary=f"{_label(rx.items)} sent to {pharmacy.name}", when=now)
    return record_service.prescription_to_out(rx)


def discard_draft(session: Session, actor: Actor, prescription_id: int) -> None:
    rx = _own_draft(session, actor, prescription_id)
    activity_service.record(session, actor, patient_id=rx.patient_id, event="prescription_draft_discarded",
                            resource_type="prescriptions", resource_id=rx.id, on_timeline=False,
                            action=AuditAction.RECORD_UPDATED)
    session.delete(rx)
    session.flush()


def get_prescription(session: Session, actor: Actor, prescription_id: int) -> PrescriptionOut:
    """Authors see their own (incl. drafts); others need consent covering prescriptions."""
    rx = session.get(Prescription, prescription_id)
    if rx is None:
        raise access_service.AccessDenied("Prescription not found")
    if rx.provider_id == actor.id and rx.organization_id == actor.organization_id:
        return record_service.prescription_to_out(rx)
    if rx.status == PrescriptionStatus.DRAFT:
        raise access_service.AccessDenied("Drafts are private to their author")
    access_service.require(session, actor, rx.patient_id, RecordCategory.PRESCRIPTIONS)
    return record_service.prescription_to_out(rx)


def patient_allergies(session: Session, actor: Actor, patient_id: int) -> list[str]:
    """Allergies are visible to any doctor with an active consent (needed for safe prescribing)."""
    _require_doctor_access(session, actor, patient_id)
    return list(session.get(Patient, patient_id).allergies)


def patient_consultations(session: Session, actor: Actor, patient_id: int) -> list:
    """This doctor's finalized consultations with the patient here — for linking a prescription."""
    _require_doctor_access(session, actor, patient_id)
    rows = session.scalars(select(Consultation).where(
        Consultation.patient_id == patient_id, Consultation.provider_id == actor.id,
        Consultation.organization_id == actor.organization_id, Consultation.status == ConsultationStatus.FINAL,
    ).order_by(Consultation.date.desc()))
    return [record_service.consultation_to_out(c) for c in rows]
