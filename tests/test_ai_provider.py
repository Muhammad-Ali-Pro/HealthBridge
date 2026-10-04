"""AI provider abstraction (Gemini), BYOK key handling and the copilot running on a provider — all offline.

The Gemini SDK client is replaced with a fake at `agents.providers._make_gemini_client`, so no network call is
made and no real key is needed. Everything else (GeminiProvider, config building, error mapping, LangGraph
agents, consent, storage, Streamlit UI) is the real code.
"""

import dataclasses
import inspect
import json
import logging
from types import SimpleNamespace

import pytest
from google.genai import errors
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from agents import copilot as copilot_graph, providers
from agents.providers import AIProvider, AIUnavailable, GeminiProvider, build_provider, mask_key
from agents.schemas import ClinicalSummary, ReviewOutput
from core.config import ROOT_DIR
from core.db import get_session
from core.models import AIFlag, Base, Organization, Role
from services import consent_service, copilot_service
from services.access_service import AccessDenied

SECRET = "AIzaTEST-not-a-real-key-7Q9Z"


class FakeModels:
    def __init__(self, owner):
        self.owner = owner

    def generate_content(self, model, contents, config):
        o = self.owner
        o.calls.append({"model": model, "contents": contents, "config": config})
        if o.errors:
            raise o.errors.pop(0)
        system = getattr(config, "system_instruction", None) or ""
        if not system:
            return SimpleNamespace(text="OK")                                   # connection probe
        if "consistency reviewer" in system:
            return SimpleNamespace(text=json.dumps(o.review))
        return SimpleNamespace(text=json.dumps(o.summary))


class FakeGeminiClient:
    def __init__(self, summary=None, review=None, errors_=None):
        self.calls, self.errors = [], list(errors_ or [])
        self.summary = summary or {
            "active_conditions": [{"text": "Documented diagnosis: Type 2 diabetes", "sources": ["PROFILE"]}],
            "recent_history": [{"text": "Invented visit", "sources": ["C-99999"]}],   # unsupported → removed
        }
        self.review = review or {"items": [{
            "severity": "medium", "category": "missing_information", "issue": "Potential missing follow-up for clinician review",
            "evidence": "No follow-up documented.", "sources": ["PROFILE"], "recommendation": "Start a new drug"}]}
        self.models = FakeModels(self)


@pytest.fixture
def fake_gemini(monkeypatch):
    client = FakeGeminiClient()
    keys: list[str] = []

    def make(api_key):
        keys.append(api_key)
        return client

    monkeypatch.setattr(providers, "_make_gemini_client", make)
    client.keys = keys
    return client


@pytest.fixture
def arif(seeded, actor):
    org = seeded.scalar(select(Organization.id).where(Organization.name == "South City Hospital"))
    consent_service.grant(seeded, actor("Ahmed Khan"), provider_id=actor("Dr. Arif Hassan").id, organization_id=org,
                          scope_type="selected", categories=["consultations", "prescriptions", "medications"])
    return actor("Dr. Arif Hassan")


# --- Provider abstraction ----------------------------------------------------------------------------


def test_agents_depend_on_the_abstraction_not_a_vendor_sdk():
    for module in (copilot_graph, copilot_service):
        source = inspect.getsource(module)
        assert "google" not in source and "genai" not in source and "openai" not in source
    assert issubclass(GeminiProvider, AIProvider)
    assert set(AIProvider.__abstractmethods__) == {"generate_structured", "test_connection", "get_model_name"}


def test_gemini_provider_initializes_with_real_sdk_offline():
    p = GeminiProvider(SECRET)                      # real google-genai client; constructing it makes no request
    assert p.get_model_name() == providers.DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"
    assert SECRET not in repr(p) and SECRET not in str(vars(p))
    assert GeminiProvider(SECRET, "gemini-3.5-flash-lite").get_model_name() == "gemini-3.5-flash-lite"


def test_no_api_key_is_a_safe_configuration_state():
    for bad in (None, "", "   "):
        with pytest.raises(AIUnavailable) as exc:
            build_provider("gemini", bad)
        assert exc.value.reason == "not_configured"
    with pytest.raises(AIUnavailable) as exc:
        build_provider("openai", SECRET)               # future provider: listed, not implemented
    assert exc.value.reason == "unsupported"


def test_generate_structured_requests_json_schema_output(fake_gemini):
    p = GeminiProvider(SECRET)
    out = p.generate_structured("You are the Clinical Summary Agent", '{"records": {}}', ClinicalSummary)
    assert out == fake_gemini.summary and fake_gemini.keys == [SECRET]
    call = fake_gemini.calls[0]
    assert call["model"] == "gemini-3.8-flash"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema == ClinicalSummary.model_json_schema()
    assert call["config"].system_instruction == "You are the Clinical Summary Agent"


def test_schema_rejection_retries_once_in_plain_json_mode(fake_gemini):
    fake_gemini.errors = [errors.ClientError(400, {"error": {"code": 400, "message": "Invalid JSON schema field",
                                                             "status": "INVALID_ARGUMENT"}})]
    out = GeminiProvider(SECRET).generate_structured("consistency reviewer", "{}", ReviewOutput)
    assert out == fake_gemini.review
    assert fake_gemini.calls[1]["config"].response_json_schema is None


@pytest.mark.parametrize("error, reason", [
    (errors.ClientError(400, {"error": {"code": 400, "message": f"API key not valid: {SECRET}", "status": "INVALID_ARGUMENT"}}), "auth"),
    (errors.ClientError(429, {"error": {"code": 429, "message": f"quota {SECRET}", "status": "RESOURCE_EXHAUSTED"}}), "quota"),
    (errors.ClientError(404, {"error": {"code": 404, "message": "models/x is not found", "status": "NOT_FOUND"}}), "model"),
    (errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}), "unavailable"),
    (ConnectionError(f"proxy said {SECRET}"), "network"),
])
def test_provider_errors_become_safe_categories_without_provider_text(fake_gemini, error, reason):
    fake_gemini.errors = [error]
    with pytest.raises(AIUnavailable) as exc:
        GeminiProvider(SECRET).generate_structured("s", "u", ReviewOutput)
    assert exc.value.reason == reason
    assert SECRET not in str(exc.value) and exc.value.__cause__ is None and exc.value.__suppress_context__


def test_connection_test_success_and_friendly_failure(fake_gemini):
    ok = GeminiProvider(SECRET).test_connection()
    assert ok.ok and ok.message == "Gemini connected successfully." and ok.model == "gemini-3.8-flash"
    assert fake_gemini.calls[-1]["contents"] == providers.CONNECTION_PROBE   # no patient data in the probe
    fake_gemini.errors = [errors.ClientError(400, {"error": {"code": 400, "message": f"API key not valid {SECRET}",
                                                             "status": "INVALID_ARGUMENT"}})]
    bad = GeminiProvider(SECRET).test_connection()
    assert not bad.ok and bad.message == "Could not connect to the selected AI provider. Please check your API key and model."
    assert SECRET not in bad.message


def test_mask_key_never_reveals_more_than_last_four():
    assert mask_key(SECRET).endswith("7Q9Z") and SECRET[:-4] not in mask_key(SECRET)
    assert mask_key("short") == "•" * 12 and mask_key(None) == ""


# --- Copilot on the provider ---------------------------------------------------------------------------


def test_copilot_runs_on_gemini_with_structured_output_and_authorized_records_only(seeded, arif, pid, fake_gemini):
    result = copilot_service.generate(seeded, arif, pid("Ahmed Khan"), provider=GeminiProvider(SECRET))
    assert result.generator == "llm" and result.provider == "Google Gemini" and result.model == "gemini-3.8-flash"
    # Structured: validated Pydantic objects, unsupported statement removed, review-only wording enforced.
    assert [c.text for c in result.summary.active_conditions] == ["Documented diagnosis: Type 2 diabetes"]
    assert result.removed_unsupported == 1
    model_flag = next(i for i in result.summary.items_for_review if "missing follow-up" in i.issue)
    assert model_flag.severity == "medium" and model_flag.category == "missing_information"
    assert model_flag.sources == ["PROFILE"] and model_flag.recommendation == "Review underlying record."
    stored = seeded.get(AIFlag, model_flag.flag_id)
    assert stored.sources == ["PROFILE"] and stored.status == "open" and stored.requested_by == arif.id
    # What reached the model: only the consented categories.
    sent = " ".join(c["contents"] for c in fake_gemini.calls)
    records = json.loads(fake_gemini.calls[0]["contents"])["records"]
    assert sorted(records["authorized_categories"]) == ["consultations", "medications", "prescriptions"]
    for leaked in ("LAB-", "HealthLab", "Fatima", "Bilal", "Shellfish", SECRET):
        assert leaked not in sent


def test_unauthorized_context_never_reaches_the_provider(seeded, actor, pid, fake_gemini):
    for who in (actor("Dr. Arif Hassan"), actor("Dr. Arif Hassan", "Clifton Medical Centre")):
        with pytest.raises(AccessDenied):
            copilot_service.generate(seeded, who, pid("Ahmed Khan"), provider=GeminiProvider(SECRET))
    assert fake_gemini.calls == []


def test_quota_exhausted_falls_back_to_a_labelled_demo_response(seeded, arif, pid, fake_gemini):
    fake_gemini.errors = [errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})]
    result = copilot_service.generate(seeded, arif, pid("Ahmed Khan"), provider=GeminiProvider(SECRET))
    assert result.generator == "rule_based" and result.model is None
    assert result.notices[0].startswith("Live AI is currently unavailable") and "quota" in result.notices[0]


# --- BYOK through the real Streamlit page ---------------------------------------------------------------

APP = str(ROOT_DIR / "app.py")


@pytest.fixture
def byok_app(monkeypatch, fake_gemini):
    """AI enabled, no developer key: the tester must bring their own."""
    from ui import ai_settings

    monkeypatch.setattr(ai_settings, "settings", dataclasses.replace(ai_settings.settings, ai_enabled=True,
                                                                      gemini_api_key=None, gemini_model=None))

    def start():
        at = AppTest.from_file(APP, default_timeout=60)
        at.session_state["hb_entered"], at.session_state["hb_role"], at.session_state["hb_user_id"] = True, Role.DOCTOR, 1
        at.session_state["sel_patient"] = 1          # Dr. Ayesha (all-records consent) · Ahmed Khan
        at.run()
        at.switch_page("views/doctor/ai_insights.py")
        at.run()
        return at
    return start


def markup(at) -> str:
    return " ".join(m.value for m in at.markdown)


def all_db_text() -> str:
    with get_session() as s:
        return " ".join(str(s.execute(select(t)).all()) for t in Base.metadata.sorted_tables)


def test_no_key_shows_configure_state_not_an_error(byok_app):
    at = byok_app()
    assert not at.exception
    html = markup(at)
    assert "AI is not connected." in html and "Enter your own Gemini API key" in html
    assert "Configure AI" in [b.label for b in at.button]
    assert "Generate Clinical Summary" not in [b.label for b in at.button]


def test_demo_run_without_key_is_labelled_as_demo(byok_app):
    at = byok_app()
    next(b for b in at.button if b.label == "Run demo analysis (no live AI)").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    html = markup(at)
    assert "Demo AI response — live model unavailable" in html
    assert "AI-generated — clinician verification required" not in html


def test_byok_connect_generate_clear_and_key_never_persisted_or_logged(byok_app, fake_gemini, caplog):
    caplog.set_level(logging.DEBUG)
    at = byok_app()
    next(b for b in at.button if b.label == "Configure AI").click()
    at.run()
    assert at.selectbox(key="aiins_ai_model").value == "gemini-3.8-flash"
    at.text_input(key="aiins_ai_key").set_value(SECRET)
    next(b for b in at.button if b.label == "Connect & Test").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    html = markup(at)
    assert "✓ Gemini connected successfully." in html and "✓ AI provider connected" in html
    assert "Active model:" in html and "gemini-3.8-flash" in html and mask_key(SECRET) in html
    assert at.session_state["_hb_byok"]["key"] == SECRET          # session memory only

    next(b for b in at.button if b.label == "Generate Clinical Summary").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    html = markup(at)
    assert "AI-generated — clinician verification required" in html and "Google Gemini · gemini-3.8-flash" in html
    assert "Based on" in html and "consented record" in html
    assert {"Accept", "Dismiss", "View source"} <= {b.label for b in at.button}

    # Never displayed in full, never stored, never logged.
    shown = html + " ".join(str(getattr(e, "value", "")) for e in at.text_input)
    assert SECRET not in shown
    assert SECRET not in all_db_text()
    assert all(SECRET not in r.getMessage() for r in caplog.records)
    assert fake_gemini.keys and set(fake_gemini.keys) == {SECRET}

    # A different browser session never sees it.
    other = byok_app()
    assert "AI is not connected." in markup(other) and other.session_state["_hb_byok"]["key"] is None

    # Clear API Key (the AI Configuration card is still open) removes it from the session.
    next(b for b in at.button if b.label == "Clear API Key").click()
    at.run()
    assert at.session_state["_hb_byok"]["key"] is None
    assert "AI is not connected." in markup(at)


def test_failed_connection_shows_friendly_message_and_keeps_no_key(byok_app, fake_gemini):
    fake_gemini.errors = [errors.ClientError(400, {"error": {"code": 400, "message": f"API key not valid {SECRET}",
                                                             "status": "INVALID_ARGUMENT"}})]
    at = byok_app()
    next(b for b in at.button if b.label == "Configure AI").click()
    at.run()
    at.text_input(key="aiins_ai_key").set_value(SECRET)
    next(b for b in at.button if b.label == "Connect & Test").click()
    at.run()
    assert not at.exception
    html = markup(at)
    assert "Could not connect to the selected AI provider. Please check your API key and model." in html
    assert SECRET not in html and at.session_state["_hb_byok"]["key"] is None
