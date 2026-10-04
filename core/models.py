"""SQLAlchemy ORM models — patient-centric.

One patient → one longitudinal timeline → many providers and organizations.

* Every clinical record keeps patient, provider (where applicable), organization and timestamp.
* Providers (doctors, pharmacists, lab staff) belong to one or more organizations via
  ProviderOrganization.
* Doctors read a patient's record only through an active, provider- AND organization-specific
  Consent, limited to the consented record categories. Pharmacies and labs only see the records
  routed to them (prescriptions / test orders).
* AI agents may only write AIFlag and AISummary rows.
"""

from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA_VERSION = 7


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_day_start_utc() -> datetime:
    """Midnight of the current LOCAL day, as naive UTC (timestamps are stored as naive UTC, shown in local time)."""
    local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


class Role(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    PHARMACIST = "pharmacist"
    LAB = "lab"


class OrgType(StrEnum):
    CLINIC = "clinic"
    HOSPITAL = "hospital"
    LABORATORY = "laboratory"
    PHARMACY = "pharmacy"


class RecordCategory(StrEnum):
    """What a patient can choose to share. Every record belongs to exactly one category."""
    CONSULTATIONS = "consultations"
    PRESCRIPTIONS = "prescriptions"
    MEDICATIONS = "medications"
    LAB_REPORTS = "lab_reports"
    HOSPITAL_RECORDS = "hospital_records"
    IMAGING_REPORTS = "imaging_reports"
    DOCUMENTS = "documents"


# Not shareable with doctors: visible only to the patient and the issuing pharmacy.
BILLING_CATEGORY = "billing"


class SourceType(StrEnum):
    """Who contributed a record to the patient's timeline."""
    PATIENT = "patient"
    PROVIDER = "provider"          # a clinician acting for an organization
    ORGANIZATION = "organization"  # a pharmacy or laboratory as an organization


class ConsentScopeType(StrEnum):
    SELECTED = "selected"
    ALL = "all"


class ConsentDuration(StrEnum):
    UNTIL_REVOKED = "until_revoked"
    ONE_CONSULTATION = "one_consultation"
    HOURS_24 = "hours_24"
    DAYS_7 = "days_7"


class ConsentStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PrescriptionStatus(StrEnum):
    DRAFT = "draft"                    # being written by the doctor
    ISSUED = "issued"                  # signed; waiting for the patient/doctor to choose a pharmacy
    SENT = "sent"                      # sent to a pharmacy, awaiting verification
    VERIFIED = "verified"              # pharmacist verified, ready to dispense
    PARTIALLY_DISPENSED = "partially_dispensed"
    DISPENSED = "dispensed"
    REJECTED = "rejected"              # pharmacy rejected, with a reason
    CANCELLED = "cancelled"            # cancelled by the prescriber


class ConsultationStatus(StrEnum):
    DRAFT = "draft"   # incomplete; visible only to its author, never part of the clinical record
    FINAL = "final"   # finalized clinical record on the patient's timeline


class DispensingStatus(StrEnum):
    DISPENSED = "dispensed"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    SUBSTITUTION_REQUESTED = "substitution_requested"  # never substituted automatically


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    CANCELLED = "cancelled"


class NoteType(StrEnum):
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    OBSERVATION = "observation"
    INTERNAL = "internal"


class DocumentType(StrEnum):
    MEDICAL_REPORT = "medical_report"
    LAB_REPORT = "lab_report"
    IMAGING_REPORT = "imaging_report"
    REFERRAL_LETTER = "referral_letter"
    DISCHARGE_SUMMARY = "discharge_summary"
    PRESCRIPTION = "prescription"
    OTHER = "other"


class PatientEntryType(StrEnum):
    NOTE = "note"
    ALLERGY = "allergy"
    CONDITION = "condition"
    MEDICATION = "medication"
    OTHER = "other"


class LabTestCategory(StrEnum):
    LAB = "lab"
    IMAGING = "imaging"


class LabOrderStatus(StrEnum):
    ORDERED = "ordered"
    RECEIVED = "received"      # sample received / test in progress
    RESULTED = "resulted"      # results entered, awaiting verification
    VERIFIED = "verified"      # verified, ready to publish
    PUBLISHED = "published"    # report published to the patient's timeline


class EventType(StrEnum):
    CONSULTATION = "consultation"
    CLINICAL_NOTE = "clinical_note"
    PRESCRIPTION_ISSUED = "prescription_issued"
    PRESCRIPTION_SENT = "prescription_sent"
    PRESCRIPTION_VERIFIED = "prescription_verified"
    PRESCRIPTION_REJECTED = "prescription_rejected"
    PRESCRIPTION_CANCELLED = "prescription_cancelled"
    DISPENSING = "dispensing"
    INVOICE_ISSUED = "invoice_issued"
    PAYMENT_RECORDED = "payment_recorded"
    INVOICE_CANCELLED = "invoice_cancelled"
    LAB_ORDERED = "lab_ordered"
    LAB_REPORT_PUBLISHED = "lab_report_published"
    DOCUMENT_ADDED = "document_added"
    PATIENT_ENTRY = "patient_entry"


class AuditAction(StrEnum):
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    RECORD_ACCESSED = "RECORD_ACCESSED"
    ACCESS_DENIED = "ACCESS_DENIED"
    RECORD_CREATED = "RECORD_CREATED"
    RECORD_UPDATED = "RECORD_UPDATED"
    AI_SUMMARY_GENERATED = "AI_SUMMARY_GENERATED"
    AI_FLAG_REVIEWED = "AI_FLAG_REVIEWED"


class FlagSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class FlagStatus(StrEnum):
    OPEN = "open"            # awaiting clinician review
    ACCEPTED = "accepted"    # clinician confirms the flag is valid and worth acting on
    DISMISSED = "dismissed"  # clinician judged the flag not relevant


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Identity and organizations
# ---------------------------------------------------------------------------


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    org_type: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255), default="")

    memberships: Mapped[list["ProviderOrganization"]] = relationship(back_populates="organization")


class User(Base):
    """Any person who signs in. Staff users (doctor/pharmacist/lab) are 'providers'."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    specialty: Mapped[str | None] = mapped_column(String(80))

    memberships: Mapped[list["ProviderOrganization"]] = relationship(back_populates="provider")
    patient_profile: Mapped["Patient | None"] = relationship(back_populates="user")


class ProviderOrganization(Base):
    """A provider can work at many organizations; an organization has many providers."""
    __tablename__ = "provider_organizations"
    __table_args__ = (UniqueConstraint("provider_id", "organization_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    title: Mapped[str] = mapped_column(String(80), default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    provider: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    dob: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(30))
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list)

    user: Mapped[User | None] = relationship(back_populates="patient_profile")
    consents: Mapped[list["Consent"]] = relationship(back_populates="patient")


# ---------------------------------------------------------------------------
# Consent (patient-controlled, provider + organization specific)
# ---------------------------------------------------------------------------


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    # Stored status is ACTIVE or REVOKED; EXPIRED is derived from expires_at / duration at check time.
    status: Mapped[str] = mapped_column(String(20), default=ConsentStatus.ACTIVE)
    scope_type: Mapped[str] = mapped_column(String(20), default=ConsentScopeType.SELECTED)
    duration: Mapped[str] = mapped_column(String(30), default=ConsentDuration.UNTIL_REVOKED)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    purpose: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    patient: Mapped[Patient] = relationship(back_populates="consents")
    provider: Mapped[User] = relationship(foreign_keys=[provider_id])
    organization: Mapped[Organization] = relationship()
    scopes: Mapped[list["ConsentScope"]] = relationship(back_populates="consent", cascade="all, delete-orphan")


class ConsentScope(Base):
    __tablename__ = "consent_scopes"
    __table_args__ = (UniqueConstraint("consent_id", "record_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    consent_id: Mapped[int] = mapped_column(ForeignKey("consents.id"))
    record_category: Mapped[str] = mapped_column(String(30))
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    consent: Mapped[Consent] = relationship(back_populates="scopes")


# ---------------------------------------------------------------------------
# Clinical records (all carry patient + provider + organization + timestamp)
# ---------------------------------------------------------------------------


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(10), default=ConsultationStatus.FINAL)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    complaint: Mapped[str] = mapped_column(Text, default="")          # reason for visit
    notes: Mapped[str] = mapped_column(Text, default="")              # symptoms / history notes
    observations: Mapped[str] = mapped_column(Text, default="")       # clinical observations / examination
    assessment: Mapped[str] = mapped_column(Text, default="")
    diagnosis: Mapped[str] = mapped_column(Text, default="")
    treatment_plan: Mapped[str] = mapped_column(Text, default="")
    follow_up: Mapped[str] = mapped_column(Text, default="")
    additional_notes: Mapped[str] = mapped_column(Text, default="")   # patient-visible extra notes

    patient: Mapped[Patient] = relationship()
    provider: Mapped[User] = relationship()
    organization: Mapped[Organization] = relationship()
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="consultation")
    clinical_notes: Mapped[list["ClinicalNote"]] = relationship(back_populates="consultation")


class ClinicalNote(Base):
    """Doctor-authored note. Clinical records are never modified by AI."""
    __tablename__ = "clinical_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"))
    note_type: Mapped[str] = mapped_column(String(20), default=NoteType.CONSULTATION)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship()
    provider: Mapped[User] = relationship()
    organization: Mapped[Organization] = relationship()
    consultation: Mapped[Consultation | None] = relationship(back_populates="clinical_notes")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))     # prescribing org
    pharmacy_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))  # fulfilling pharmacy
    status: Mapped[str] = mapped_column(String(30), default=PrescriptionStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)         # prescription date
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)                  # pharmacist verification (D7)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str] = mapped_column(Text, default="")
    status_reason: Mapped[str] = mapped_column(Text, default="")                   # rejection / cancellation reason

    consultation: Mapped[Consultation | None] = relationship(back_populates="prescriptions")
    patient: Mapped[Patient] = relationship()
    provider: Mapped[User] = relationship(foreign_keys=[provider_id])
    verifier: Mapped[User | None] = relationship(foreign_keys=[verified_by])
    organization: Mapped[Organization] = relationship(foreign_keys=[organization_id])
    pharmacy: Mapped[Organization | None] = relationship(foreign_keys=[pharmacy_id])
    items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")
    dispensings: Mapped[list["Dispensing"]] = relationship(back_populates="prescription")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="prescription")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"))
    drug_name: Mapped[str] = mapped_column(String(120))
    strength: Mapped[str] = mapped_column(String(60))                 # e.g. "500 mg"
    dosage: Mapped[str] = mapped_column(String(60), default="")       # e.g. "1 tablet"
    route: Mapped[str] = mapped_column(String(40), default="oral")
    frequency: Mapped[str] = mapped_column(String(80))
    duration_days: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str] = mapped_column(Text, default="")

    prescription: Mapped[Prescription] = relationship(back_populates="items")


class Dispensing(Base):
    __tablename__ = "dispensings"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"))
    pharmacist_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    dispensed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(30), default=DispensingStatus.DISPENSED)
    # One line per prescribed medicine (D6):
    # [{"item_id": int, "drug_name": str, "quantity_prescribed": int, "quantity_dispensed": int,
    #   "status": DispensingStatus, "note": str (pharmacy-internal)}]
    # Dispensing.status is the aggregate of the lines. `notes` and line notes are pharmacy-internal.
    items_dispensed: Mapped[list[dict]] = mapped_column(JSON, default=list)
    substitutions: Mapped[str] = mapped_column(Text, default="")   # substitution REQUEST text; never automatic
    notes: Mapped[str] = mapped_column(Text, default="")

    prescription: Mapped[Prescription] = relationship(back_populates="dispensings")
    pharmacist: Mapped[User] = relationship()
    organization: Mapped[Organization] = relationship()


class Invoice(Base):
    """Simulated pharmacy billing — no payment gateway."""
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(30), unique=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"))
    dispensing_id: Mapped[int | None] = mapped_column(ForeignKey("dispensings.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))   # pharmacy
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # [{"description": str, "quantity": int, "unit_price": float, "total": float}]  — one invoice per dispensing (D13)
    items: Mapped[list[dict]] = mapped_column(JSON, default=list)
    total: Mapped[float] = mapped_column(default=0.0)
    amount_paid: Mapped[float] = mapped_column(default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    payment_status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    prescription: Mapped[Prescription] = relationship(back_populates="invoices")
    patient: Mapped[Patient] = relationship()
    organization: Mapped[Organization] = relationship()


class LabOrder(Base):
    __tablename__ = "lab_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))                   # ordering provider
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))       # ordering org
    lab_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))                # performing lab
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"))
    test_name: Mapped[str] = mapped_column(String(120))
    test_category: Mapped[str] = mapped_column(String(20), default=LabTestCategory.LAB)
    priority: Mapped[str] = mapped_column(String(20), default="routine")
    clinical_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=LabOrderStatus.ORDERED)
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship()
    provider: Mapped[User] = relationship()
    organization: Mapped[Organization] = relationship(foreign_keys=[organization_id])
    lab: Mapped[Organization] = relationship(foreign_keys=[lab_id])
    result: Mapped["LabResult | None"] = relationship(back_populates="order", uselist=False)
    report: Mapped["LabReport | None"] = relationship(back_populates="order", uselist=False)


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_order_id: Mapped[int] = mapped_column(ForeignKey("lab_orders.id"), unique=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))       # performing lab
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    # [{"analyte": str, "value": str, "unit": str, "reference": str, "flag": "high"|"low"|"normal"}]
    values: Mapped[list[dict]] = mapped_column(JSON, default=list)
    interpretation: Mapped[str] = mapped_column(Text, default="")
    lab_notes: Mapped[str] = mapped_column(Text, default="")

    order: Mapped[LabOrder] = relationship(back_populates="result")


class LabReport(Base):
    """The published report. Publication is what places a result on the patient's timeline."""
    __tablename__ = "lab_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_number: Mapped[str] = mapped_column(String(30), unique=True)
    lab_order_id: Mapped[int] = mapped_column(ForeignKey("lab_orders.id"), unique=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))       # performing lab
    published_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    conclusion: Mapped[str] = mapped_column(Text, default="")
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))

    order: Mapped[LabOrder] = relationship(back_populates="report")


class Document(Base):
    """A file added to the patient's record by the patient or a provider/organization."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    source_type: Mapped[str] = mapped_column(String(20))                               # SourceType
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))  # None when patient-uploaded
    doc_type: Mapped[str] = mapped_column(String(30), default=DocumentType.OTHER)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    storage_path: Mapped[str | None] = mapped_column(String(500))                     # local file for the MVP
    record_category: Mapped[str] = mapped_column(String(30), default=RecordCategory.DOCUMENTS)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"))   # attachment link
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    uploader: Mapped[User] = relationship()
    organization: Mapped[Organization | None] = relationship()


class PatientEntry(Base):
    """Information the patient adds themselves — always shown as patient-provided."""
    __tablename__ = "patient_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    entry_type: Mapped[str] = mapped_column(String(20), default=PatientEntryType.NOTE)
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TimelineEvent(Base):
    """Append-only index of a patient's longitudinal record, with full provenance."""
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    record_category: Mapped[str] = mapped_column(String(30))
    ref_table: Mapped[str] = mapped_column(String(40))
    ref_id: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    source_type: Mapped[str] = mapped_column(String(20), default=SourceType.PROVIDER)
    summary: Mapped[str] = mapped_column(Text, default="")
    # False for internal clinician notes: shown to authorized clinicians, never to the patient.
    patient_visible: Mapped[bool] = mapped_column(Boolean, default=True)

    actor: Mapped[User | None] = relationship()
    organization: Mapped[Organization | None] = relationship()


# ---------------------------------------------------------------------------
# AI outputs (the only tables agents may write)
# ---------------------------------------------------------------------------


class AIFlag(Base):
    __tablename__ = "ai_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"))
    severity: Mapped[str] = mapped_column(String(20), default=FlagSeverity.WARNING)
    category: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=FlagStatus.OPEN)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str] = mapped_column(Text, default="")
    # Flags are derived from ONE doctor's consent scope in ONE organization — visible only there.
    summary_id: Mapped[int | None] = mapped_column(ForeignKey("ai_summaries.id"))
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)   # cited record ids, e.g. ["RX-00001"]

    patient: Mapped[Patient] = relationship()


class AISummary(Base):
    __tablename__ = "ai_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_event_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    generator: Mapped[str] = mapped_column(String(20), default="fallback")
    # Who asked, and in which organization context (summaries are scoped to that consent).
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)   # structured, validated summary output


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_type: Mapped[str] = mapped_column(String(20), default="system")
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    action: Mapped[str] = mapped_column(String(40))
    resource_type: Mapped[str] = mapped_column(String(40), default="")
    resource_id: Mapped[int | None] = mapped_column(Integer)
    # "metadata" is reserved on declarative classes, so the attribute is `details`.
    details: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
