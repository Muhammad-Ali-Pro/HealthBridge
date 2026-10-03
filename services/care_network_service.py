"""The patient's Care Network: every doctor and organization connected to their timeline."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import Consent, Consultation, LabOrder, OrgType, Prescription, PrescriptionStatus, User
from core.schemas import Actor, CareDoctor, CareNetwork, CareOrganization, OrganizationOut
from services import consent_service, record_service

ORG_ORDER = [OrgType.CLINIC, OrgType.HOSPITAL, OrgType.LABORATORY, OrgType.PHARMACY]


def network(session: Session, actor: Actor) -> CareNetwork:
    record = record_service.own_record(session, actor)  # authorizes: patient's own record only
    pid = record.patient.id

    doctor_orgs: dict[int, set[str]] = defaultdict(set)
    org_rows: dict[int, object] = {}
    org_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    org_last: dict[int, object] = {}

    def touch(org, kind, when):
        org_rows[org.id] = org
        org_counts[org.id][kind] += 1
        if when and (org.id not in org_last or when > org_last[org.id]):
            org_last[org.id] = when

    for c in session.scalars(select(Consultation).where(Consultation.patient_id == pid)):
        doctor_orgs[c.provider_id].add(c.organization.name)
        touch(c.organization, "visits", c.date)
    for rx in session.scalars(select(Prescription).where(Prescription.patient_id == pid,
                                                         Prescription.status != PrescriptionStatus.DRAFT)):
        doctor_orgs[rx.provider_id].add(rx.organization.name)
        if rx.pharmacy:
            touch(rx.pharmacy, "prescriptions", rx.created_at)
    for o in session.scalars(select(LabOrder).where(LabOrder.patient_id == pid)):
        doctor_orgs[o.provider_id].add(o.organization.name)
        touch(o.lab, "tests", o.ordered_at)
    consents = consent_service.list_for_patient(session, actor)
    for c in consents:
        doctor_orgs[c.provider_id].add(c.organization_name)

    doctors = []
    for provider_id, orgs in doctor_orgs.items():
        user = session.get(User, provider_id)
        doctors.append(CareDoctor(provider_id=provider_id, name=user.name, specialty=user.specialty,
                                  organizations=sorted(orgs),
                                  consents=[c for c in consents if c.provider_id == provider_id]))
    # Organizations where the patient has consented to a doctor also belong to the network.
    for c in session.scalars(select(Consent).where(Consent.patient_id == pid)):
        org_rows.setdefault(c.organization_id, c.organization)

    def relation(org) -> str:
        n = org_counts[org.id]
        if org.org_type == OrgType.LABORATORY:
            return f"{n['tests']} test{'s' if n['tests'] != 1 else ''}"
        if org.org_type == OrgType.PHARMACY:
            return f"{n['prescriptions']} prescription{'s' if n['prescriptions'] != 1 else ''}"
        return f"{n['visits']} visit{'s' if n['visits'] != 1 else ''}" if n["visits"] else "Doctor you shared with"

    organizations = [
        CareOrganization(organization=OrganizationOut.model_validate(o), relation=relation(o), last_seen=org_last.get(o.id))
        for o in sorted(org_rows.values(), key=lambda o: (ORG_ORDER.index(o.org_type), o.name))
    ]
    return CareNetwork(doctors=sorted(doctors, key=lambda d: d.name), organizations=organizations)
