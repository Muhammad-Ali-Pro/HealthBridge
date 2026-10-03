"""Clinical Copilot: consent before AI, validated output, citations, safe failure, audit."""

import json

import pytest
from sqlalchemy import select

from agents.llm import LLMUnavailable
from agents.schemas import REVIEW_RECOMMENDATION, ClinicalSummary
from core.models import AISummary, AuditAction, AuditLog, Organization
from services import access_service, consent_service, copilot_service
from services.access_service import AccessDenied


@pytest.fixture
def arif(seeded, actor):
    org = seeded.scalar(select(Organization.id).where(Organization.name == "South City Hospital"))
    consent_service.grant(seeded, actor("Ahmed Khan"), provider_id=actor("Dr. Arif Hassan").id, organization_id=org,
                          scope_type="selected", categories=["consultations", "prescriptions", "medications"])
    return actor("Dr. Arif Hassan")


class FakeLLM:
    """Records exactly what the AI would receive; returns canned JSON per agent."""

    def __init__(self, summary: dict | None = None, review: dict | None = None, fail: bool = False):
        self.calls: list[str] = []
        self.summary, self.review, self.fail = summary, review, fail

    def __call__(self, system: str, user: str) -> dict:
        self.calls.append(user)
        if self.fail:
            raise LLMUnavailable("network down")
        return self.review if "consistency reviewer" in system else self.summary


def valid_summary(rx_id: str) -> dict:
    return {
        "patient_snapshot": {"age": 1, "sex": "x", "allergies": [], "patient_provided": []},
        "active_conditions": [{"text": "Documented diagnosis: Type 2 diabetes", "sources": ["PROFILE"]},
                              {"text": "Invented condition", "sources": ["C-99999"]}],
        "current_medications": [{"medicine": "Metformin", "strength": "500 mg", "dosage": "1 tablet",
                                 "frequency": "twice daily", "date": "x", "sources": [rx_id]}],
        "recent_history": [], "recent_prescriptions": [], "important_reports": [], "items_for_review": [],
    }


def test_ai_receives_only_authorized_records(seeded, arif, pid):
    rx_id = "RX-00002"
    fake = FakeLLM(summary=valid_summary(rx_id), review={"items": []})
    copilot_service.generate(seeded, arif, pid("Ahmed Khan"), llm=fake)
    payload = json.loads(fake.calls[0])["records"]
    assert sorted(payload["authorized_categories"]) == ["consultations", "medications", "prescriptions"]
    assert payload["lab_reports"] == [] and payload["documents"] == [] and payload["patient_provided"] == []
    orgs = {c["organization"] for c in payload["consultations"]}
    assert "City Hospital" not in orgs  # hospital records were not shared
    text = json.dumps(payload)
    # Unshared categories (labs, hospital records, documents, patient entries) and other patients never appear.
    for leaked in ("Fatima", "Bilal", "Shellfish", "LAB-", "HealthLab", "Day-unit", "Dizziness", "Renal"):
        assert leaked not in text


def test_ai_cannot_run_without_consent_and_never_sees_data(seeded, actor, pid):
    fake = FakeLLM(summary={}, review={})
    with pytest.raises(AccessDenied):
        copilot_service.generate(seeded, actor("Dr. Arif Hassan"), pid("Ahmed Khan"), llm=fake)
    with pytest.raises(AccessDenied):  # same doctor, other organization
        copilot_service.generate(seeded, actor("Dr. Arif Hassan", "Clifton Medical Centre"), pid("Ahmed Khan"), llm=fake)
    assert fake.calls == []


def test_ai_output_is_validated_and_unsupported_citations_removed(seeded, arif, pid):
    review = {"items": [{"severity": "low", "issue": "Potential date inconsistency for clinician review",
                         "evidence": "x", "sources": ["C-99999"], "recommendation": "Increase the dose"}]}
    result = copilot_service.generate(seeded, arif, pid("Ahmed Khan"), llm=FakeLLM(valid_summary("RX-00002"), review))
    assert result.generator == "llm"
    ClinicalSummary.model_validate(result.summary.model_dump())
    assert [c.text for c in result.summary.active_conditions] == ["Documented diagnosis: Type 2 diabetes"]
    assert result.removed_unsupported == 1
    assert result.summary.patient_snapshot.age == 48 and result.summary.patient_snapshot.sex == "male"
    assert all(i.recommendation == REVIEW_RECOMMENDATION for i in result.summary.items_for_review)
    assert any("metformin" in i.issue.lower() for i in result.summary.items_for_review)  # rule-based baseline kept


def test_ai_failure_falls_back_without_breaking(seeded, arif, pid):
    result = copilot_service.generate(seeded, arif, pid("Ahmed Khan"), llm=FakeLLM(fail=True))
    assert result.generator == "rule_based"
    assert "temporarily unavailable" in result.notices[0]
    assert result.summary.current_medications and result.summary.recent_history


def test_invalid_ai_output_is_discarded_safely(seeded, arif, pid):
    result = copilot_service.generate(seeded, arif, pid("Ahmed Khan"),
                                      llm=FakeLLM(summary={"current_medications": "oops"}, review={"items": []}))
    assert result.generator == "rule_based" and "validation" in result.notices[0]


def test_rule_based_review_flags_documentation_discrepancies(seeded, actor, pid):
    result = copilot_service.generate(seeded, actor("Dr. Ayesha Malik"), pid("Ahmed Khan"), llm=None)
    issues = " | ".join(i.issue for i in result.summary.items_for_review)
    assert "Potential medication documentation discrepancy" in issues          # Metformin 850 vs 500
    assert "Allergy documentation inconsistency" in issues                     # self-reported shellfish
    med_flag = next(i for i in result.summary.items_for_review if "Metformin" in i.issue)
    assert set(med_flag.sources) <= {s.id for s in result.sources}
    assert all(i.recommendation == REVIEW_RECOMMENDATION for i in result.summary.items_for_review)


def test_ai_summary_is_audited_scoped_and_hidden_after_revocation(seeded, arif, actor, pid):
    ahmed = pid("Ahmed Khan")
    result = copilot_service.generate(seeded, arif, ahmed, llm=None)
    entry = seeded.scalars(select(AuditLog).where(AuditLog.action == AuditAction.AI_SUMMARY_GENERATED)).one()
    assert entry.actor_id == arif.id and entry.organization_id == arif.organization_id and entry.patient_id == ahmed
    assert set(entry.details) == {"generator", "scope", "record_counts", "items_for_review"}  # no prompt/content
    row = seeded.scalars(select(AISummary)).one()
    assert row.requested_by == arif.id and row.organization_id == arif.organization_id
    assert copilot_service.latest(seeded, arif, ahmed).generated_at == result.generated_at

    consent_id = access_service.authorize(seeded, arif, ahmed).consent_id
    consent_service.revoke(seeded, actor("Ahmed Khan"), consent_id)
    with pytest.raises(AccessDenied):
        copilot_service.latest(seeded, arif, ahmed)
