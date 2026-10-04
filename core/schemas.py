"""Pydantic schemas returned by the service layer (the UI never receives ORM rows)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, computed_field

from core.models import ConsentScopeType, ConsentStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Identity, organizations, acting context
# ---------------------------------------------------------------------------


class UserOut(ORMModel):
    id: int
    name: str
    role: str
    specialty: str | None = None


class OrganizationOut(ORMModel):
    id: int
    name: str
    org_type: str
    address: str


class MembershipOut(BaseModel):
    organization: OrganizationOut
    title: str
    is_primary: bool


class Actor(BaseModel):
    """Who is acting, and in which organization context (None for patients)."""
    user: UserOut
    organization: OrganizationOut | None = None

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def organization_id(self) -> int | None:
        return self.organization.id if self.organization else None


class ProviderOption(BaseModel):
    """A provider in a specific organization context — the unit a patient grants consent to."""
    provider_id: int
    provider_name: str
    specialty: str | None
    organization_id: int
    organization_name: str
    organization_type: str


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------


class PatientIdentity(ORMModel):
    """The minimum needed to identify a patient. Never includes clinical data."""
    id: int
    name: str
    dob: date
    sex: str

    @computed_field
    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    @computed_field
    @property
    def display_id(self) -> str:
        return f"HB-{self.id:06d}"


class PatientOut(PatientIdentity):
    user_id: int | None = None
    allergies: list[str]
    conditions: list[str] | None  # None = not shared with this viewer


# ---------------------------------------------------------------------------
# Consent and access
# ---------------------------------------------------------------------------


class ConsentOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    provider_id: int
    provider_name: str
    organization_id: int
    organization_name: str
    organization_type: str
    status: str          # effective status: active / revoked / expired
    scope_type: str
    categories: list[str]
    duration: str
    granted_at: datetime
    revoked_at: datetime | None
    expires_at: datetime | None
    purpose: str

    @computed_field
    @property
    def display_id(self) -> str:
        return f"CON-{self.id:06d}"

    @property
    def active(self) -> bool:
        return self.status == ConsentStatus.ACTIVE


class AccessDecision(BaseModel):
    allowed: bool
    via: str                      # "self" | "consent" | "none"
    reason: str
    patient_id: int
    consent_id: int | None = None
    scope_type: str | None = None
    categories: list[str] = []

    def can(self, category: str) -> bool:
        if not self.allowed:
            return False
        if category == "billing":  # billing is never shareable, even with "all records"
            return self.via == "self"
        return self.scope_type == ConsentScopeType.ALL or category in self.categories


class DirectoryEntry(BaseModel):
    patient: PatientIdentity
    access: AccessDecision


# ---------------------------------------------------------------------------
# Clinical records
# ---------------------------------------------------------------------------


def source_label(source_type: str, actor_name: str | None, organization_name: str | None) -> str:
    """'Patient' · 'Dr. Arif Hassan / South City Hospital' · 'HealthLab Diagnostics'."""
    if source_type == "patient":
        return "Patient"
    if source_type == "provider" and actor_name and organization_name:
        return f"{actor_name} / {organization_name}"
    return organization_name or actor_name or "HealthBridge"


class TimelineEventOut(ORMModel):
    id: int
    patient_id: int
    event_type: str
    record_category: str
    ref_table: str
    ref_id: int
    occurred_at: datetime
    actor_id: int | None
    actor_name: str | None = None
    organization_name: str | None = None
    organization_type: str | None = None
    source_type: str
    summary: str
    patient_visible: bool = True

    @computed_field
    @property
    def source(self) -> str:
        return source_label(self.source_type, self.actor_name, self.organization_name)


class ConsultationOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    provider_name: str
    organization_name: str
    organization_type: str
    record_category: str
    date: datetime
    status: str = "final"
    updated_at: datetime | None = None
    complaint: str
    notes: str
    observations: str = ""
    assessment: str
    diagnosis: str = ""
    treatment_plan: str = ""
    follow_up: str = ""
    additional_notes: str = ""


class ClinicalNoteOut(BaseModel):
    id: int
    patient_id: int
    provider_name: str
    organization_name: str
    organization_type: str
    record_category: str
    consultation_id: int | None
    note_type: str
    content: str
    created_at: datetime


class DocumentOut(BaseModel):
    id: int
    patient_id: int
    source_type: str
    uploaded_by_name: str
    organization_name: str | None
    organization_type: str | None
    doc_type: str
    title: str
    description: str
    file_name: str | None
    mime_type: str | None
    size_bytes: int | None
    record_category: str
    created_at: datetime
    has_file: bool = False
    consultation_id: int | None = None

    @computed_field
    @property
    def source(self) -> str:
        if self.source_type == "patient":
            return "Patient uploaded"
        return f"Uploaded by {self.organization_name or self.uploaded_by_name}"


class PatientEntryOut(ORMModel):
    id: int
    patient_id: int
    entry_type: str
    title: str
    details: str
    created_at: datetime


class PrescriptionItemOut(ORMModel):
    drug_name: str
    strength: str
    dosage: str
    route: str
    frequency: str
    duration_days: int
    quantity: int
    instructions: str


class DispensingOut(BaseModel):
    id: int
    pharmacist_name: str
    pharmacy_name: str
    dispensed_at: datetime
    status: str
    items: list[dict]
    substitutions: str
    notes: str


class InvoiceOut(BaseModel):
    id: int
    invoice_number: str
    prescription_id: int
    patient_id: int
    patient_name: str
    pharmacy_name: str
    items: list[dict]
    total: float
    amount_paid: float
    currency: str
    payment_status: str
    created_at: datetime


class PrescriptionOut(BaseModel):
    """Also used for the pharmacy's minimum-necessary view (reason is None there)."""
    id: int
    consultation_id: int | None
    patient_id: int
    patient_name: str
    patient_age: int
    patient_sex: str
    patient_allergies: list[str]
    provider_name: str
    organization_name: str
    organization_type: str
    pharmacy_name: str | None
    status: str
    created_at: datetime
    issued_at: datetime | None = None
    sent_at: datetime | None = None
    dispensed_at: datetime | None
    reason: str | None
    notes: str = ""
    status_reason: str = ""
    items: list[PrescriptionItemOut]
    dispensings: list[DispensingOut] = []
    invoice: InvoiceOut | None = None

    @computed_field
    @property
    def display_id(self) -> str:
        return f"RX-{self.id:05d}"


class MedicationOut(BaseModel):
    prescription_id: int
    drug_name: str
    strength: str
    dosage: str = ""
    frequency: str
    started: datetime
    ends: datetime
    prescribed_by: str
    organization_name: str
    status: str
    current: bool


class LabValueOut(BaseModel):
    analyte: str
    value: str
    unit: str = ""
    reference: str = ""
    flag: str = "normal"


class LabOrderOut(BaseModel):
    id: int
    patient: PatientIdentity
    provider_name: str
    organization_name: str
    organization_type: str
    lab_name: str
    test_name: str
    test_category: str
    record_category: str
    priority: str
    clinical_notes: str
    status: str
    ordered_at: datetime
    values: list[LabValueOut] = []
    interpretation: str = ""
    lab_notes: str = ""
    entered_at: datetime | None = None
    verified_at: datetime | None = None
    published_at: datetime | None = None
    report_number: str | None = None

    @computed_field
    @property
    def display_id(self) -> str:
        return f"LAB-{self.id:05d}"


class AuthorizedRecord(BaseModel):
    """A patient's record, filtered to exactly what the viewer is allowed to see."""
    patient: PatientOut
    access: AccessDecision
    consultations: list[ConsultationOut]
    notes: list[ClinicalNoteOut] = []
    prescriptions: list[PrescriptionOut]
    medications: list[MedicationOut]
    reports: list[LabOrderOut]
    documents: list[DocumentOut] = []
    patient_entries: list[PatientEntryOut] = []   # patient-provided; shared under "documents"
    timeline: list[TimelineEventOut]


# ---------------------------------------------------------------------------
# Care network, audit, AI
# ---------------------------------------------------------------------------


class CareDoctor(BaseModel):
    provider_id: int
    name: str
    specialty: str | None
    organizations: list[str]
    consents: list[ConsentOut]


class CareOrganization(BaseModel):
    organization: OrganizationOut
    relation: str            # e.g. "2 consultations", "Fills your prescriptions"
    last_seen: datetime | None


class CareNetwork(BaseModel):
    doctors: list[CareDoctor]
    organizations: list[CareOrganization]


class AuditEntryOut(BaseModel):
    id: int
    action: str
    actor_name: str | None
    actor_type: str
    patient_name: str | None
    provider_name: str | None
    organization_name: str | None
    resource_type: str
    resource_id: int | None
    details: dict
    timestamp: datetime


class AIFlagOut(ORMModel):
    id: int
    patient_id: int
    patient_name: str = ""
    prescription_id: int | None
    severity: str
    category: str
    message: str
    evidence: dict = {}
    sources: list[str] = []
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_name: str | None = None
    review_note: str = ""
    summary_id: int | None = None
    organization_id: int | None = None


class SourceDetail(BaseModel):
    """'View source' for an AI statement: the underlying record, resolved through consent again."""
    id: str
    record_type: str
    date: datetime | None
    organization_name: str | None
    organization_type: str | None
    provider_name: str | None
    title: str
    excerpt: str
    available: bool = True


class AISummaryOut(ORMModel):
    id: int
    patient_id: int
    content: str
    generated_at: datetime
    generator: str
    requested_by: int | None = None
    organization_id: int | None = None
    payload: dict = {}
