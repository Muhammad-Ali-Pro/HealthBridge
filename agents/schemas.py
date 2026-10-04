"""Validated output contract of the HealthBridge Clinical Copilot."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

REVIEW_RECOMMENDATION = "Review underlying record."
NOT_DOCUMENTED = "Not available in the authorized records."
DISCLAIMER = ("AI organises, summarises and flags possible discrepancies. It does not diagnose or change treatment. "
              "A clinician must verify every finding.")
FLAG_CATEGORIES = ("medication_discrepancy", "duplicate_medication", "allergy_documentation", "allergy_conflict",
                   "missing_information", "date_inconsistency", "other")


class SourcedItem(BaseModel):
    text: str = Field(min_length=1, max_length=800)
    sources: list[str] = []


class MedicationItem(BaseModel):
    medicine: str = Field(min_length=1)
    strength: str = NOT_DOCUMENTED
    dosage: str = NOT_DOCUMENTED
    frequency: str = NOT_DOCUMENTED
    date: str = NOT_DOCUMENTED
    sources: list[str] = []


class PatientSnapshot(BaseModel):
    age: int | None = None
    sex: str | None = None
    allergies: list[SourcedItem] = []
    patient_provided: list[SourcedItem] = []


class ReviewItem(BaseModel):
    """One Safety/Consistency flag: severity, description (issue), reason (evidence) and source records."""
    severity: Literal["low", "medium", "high"]
    category: str = "other"
    issue: str = Field(min_length=1, max_length=600)
    evidence: str = Field(default="", max_length=1200)
    sources: list[str] = []
    recommendation: str = REVIEW_RECOMMENDATION
    flag_id: int | None = None   # set by HealthBridge when the flag is stored for clinician review

    @field_validator("category", mode="before")
    @classmethod
    def _known_category(cls, value):
        return value if value in FLAG_CATEGORIES else "other"

    @field_validator("recommendation", mode="before")
    @classmethod
    def _never_clinical_advice(cls, _value):
        # The copilot never recommends treatment — whatever a model produced, the action is a record review.
        return REVIEW_RECOMMENDATION


class ClinicalSummary(BaseModel):
    patient_snapshot: PatientSnapshot = PatientSnapshot()
    active_conditions: list[SourcedItem] = []
    current_medications: list[MedicationItem] = []
    recent_history: list[SourcedItem] = []
    recent_prescriptions: list[SourcedItem] = []
    important_changes: list[SourcedItem] = []
    follow_up: list[SourcedItem] = []
    important_reports: list[SourcedItem] = []
    items_for_review: list[ReviewItem] = []


class ReviewOutput(BaseModel):
    items: list[ReviewItem] = []


class SourceRef(BaseModel):
    id: str
    kind: str
    label: str
    date: str


class CopilotResult(BaseModel):
    patient_name: str
    patient_display_id: str
    provider_name: str
    organization_name: str
    authorized_categories: list[str]
    summary: ClinicalSummary
    sources: list[SourceRef]
    generator: Literal["llm", "rule_based"]   # llm = live model output; rule_based = labelled demo response
    provider: str | None = None             # e.g. "Google Gemini" — only when the live model produced the summary
    model: str | None = None                # e.g. "gemini-3.8-flash"
    notices: list[str] = []
    removed_unsupported: int = 0
    record_counts: dict[str, int] = {}
    retrieval: dict[str, int] = {}      # Record Retrieval Agent output per category (0 = not consented / none)
    summary_id: int | None = None
    generated_at: datetime
    disclaimer: str = DISCLAIMER
