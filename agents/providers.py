"""Provider-independent AI layer for the HealthBridge Clinical Copilot.

    AIProvider (abstract)
    ├── GeminiProvider   implemented (Google Gemini API, google-genai SDK)
    └── OpenAIProvider   future — add a subclass + one PROVIDERS entry; agents, graph, UI and schemas stay unchanged

The LangGraph agents only ever call `generate_structured(system, user, schema)`; nothing outside this module
imports a provider SDK.

API keys: a provider keeps its key privately in memory for the lifetime of the object. It never logs it, never
includes it in repr() or in error messages, and HealthBridge never writes it to the database. Errors are
reduced to a safe category (`AIUnavailable.reason`) so raw provider text — which could echo request details —
is never shown or stored.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel

# Safe, user-facing messages. Nothing provider-generated is ever shown.
REASONS = {
    "not_configured": "AI is not connected. Enter your own Gemini API key to enable the AI Clinical Copilot.",
    "disabled": "AI is disabled for this deployment (AI_ENABLED=false).",
    "auth": "Could not connect to the selected AI provider. Please check your API key and model.",
    "model": "Could not connect to the selected AI provider. Please check your API key and model.",
    "quota": "The AI provider's rate limit or free-tier quota has been reached. Try again in a minute.",
    "unavailable": "The AI provider is temporarily unavailable. Please try again shortly.",
    "network": "Could not reach the AI provider. Check your internet connection.",
    "invalid_output": "The AI provider returned output that could not be read.",
    "unsupported": "This AI provider is not available yet.",
}


class AIUnavailable(RuntimeError):
    """Live AI could not be used. `reason` is a key of REASONS; the message never contains provider text."""

    def __init__(self, reason: str):
        self.reason = reason if reason in REASONS else "unavailable"
        super().__init__(REASONS[self.reason])


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str
    model: str


class AIProvider(ABC):
    """What the Copilot agents depend on. Implementations translate to one vendor's API."""

    name: str = ""        # registry id, e.g. "gemini"
    label: str = ""       # display name, e.g. "Google Gemini"

    @abstractmethod
    def generate_structured(self, system: str, user: str, schema: type[BaseModel]) -> dict:
        """Return one JSON object conforming to `schema`. Raises AIUnavailable on any failure."""

    @abstractmethod
    def test_connection(self) -> ConnectionResult:
        """Make a minimal, data-free request. Never raises; never includes provider text in the message."""

    @abstractmethod
    def get_model_name(self) -> str:
        ...

    def __repr__(self) -> str:  # never show credentials
        return f"{type(self).__name__}(model={self.get_model_name()!r})"


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

# Default demo model. Verified on 2026-10-04 against ai.google.dev: listed as "Free of charge" on the Gemini API
# free tier (pricing page, updated 2026-10-01) and as the current stable Flash model (models page).
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
# Other stable models also listed on the free tier — offered in the AI Configuration panel.
GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite")

CONNECTION_PROBE = "Reply with the single word OK."   # no patient data is ever used to test a connection


def _make_gemini_client(api_key: str):
    """Build the SDK client (separate function so tests can substitute an offline fake)."""
    from google import genai
    from google.genai import types

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60_000))


def _gemini_reason(exc: Exception) -> str:
    """Map an SDK/network error to a safe category. The raw message is inspected here only, never surfaced."""
    try:
        from google.genai import errors
    except ImportError:  # pragma: no cover
        errors = None
    code = getattr(exc, "code", None)
    text = str(exc).lower()
    if errors is not None and isinstance(exc, errors.ClientError):
        if code in (401, 403) or _mentions_key(exc):
            return "auth"
        if code == 404:
            return "model"
        if code == 429:
            return "quota"
        return "model" if "model" in text else "auth"
    if errors is not None and isinstance(exc, errors.ServerError):
        return "unavailable"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "invalid_output"
    return "network"


def _mentions_key(exc: Exception) -> bool:
    text = str(exc).lower()
    return "api key" in text or "api_key" in text


class GeminiProvider(AIProvider):
    name = "gemini"
    label = "Google Gemini"

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key or not api_key.strip():
            raise AIUnavailable("not_configured")
        self.__model = (model or DEFAULT_GEMINI_MODEL).strip()
        self.__client = _make_gemini_client(api_key.strip())   # the key lives only inside this client object

    def get_model_name(self) -> str:
        return self.__model

    def _config(self, system: str | None, schema: type[BaseModel] | None):
        from google.genai import types

        kwargs: dict = {"response_mime_type": "application/json"} if schema is not None else {}
        if schema is not None:
            kwargs["response_json_schema"] = schema.model_json_schema()
        if system:
            kwargs["system_instruction"] = system
        return types.GenerateContentConfig(**kwargs)

    def _call(self, contents: str, config):
        return self.__client.models.generate_content(model=self.__model, contents=contents, config=config)

    def generate_structured(self, system: str, user: str, schema: type[BaseModel]) -> dict:
        try:
            try:
                response = self._call(user, self._config(system, schema))
            except Exception as exc:
                # Some models reject parts of a JSON schema (400). The schema is also in the prompt, so retry
                # once with plain JSON mode; Pydantic validates the result either way.
                if getattr(exc, "code", None) != 400 or _mentions_key(exc):
                    raise
                from google.genai import types

                response = self._call(user, types.GenerateContentConfig(
                    system_instruction=system, response_mime_type="application/json"))
            data = json.loads(response.text or "")
        except AIUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — every failure becomes a safe category
            raise AIUnavailable(_gemini_reason(exc)) from None   # `from None`: don't chain provider text
        if not isinstance(data, dict):
            raise AIUnavailable("invalid_output")
        return data

    def test_connection(self) -> ConnectionResult:
        try:
            response = self._call(CONNECTION_PROBE, self._config(None, None))
            if not (response.text or "").strip():
                raise ValueError("empty")
        except Exception as exc:  # noqa: BLE001
            reason = exc.reason if isinstance(exc, AIUnavailable) else _gemini_reason(exc)
            if reason == "invalid_output":
                reason = "model"
            return ConnectionResult(False, REASONS[reason], self.__model)
        return ConnectionResult(True, "Gemini connected successfully.", self.__model)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, type[AIProvider]] = {"gemini": GeminiProvider}
# Shown in the UI but not implemented in Phase 2. Adding OpenAI = an OpenAIProvider subclass + a PROVIDERS entry.
FUTURE_PROVIDERS = {"openai": "OpenAI (coming later)"}


def build_provider(provider: str, api_key: str | None, model: str | None = None) -> AIProvider:
    cls = PROVIDERS.get((provider or "").lower())
    if cls is None:
        raise AIUnavailable("unsupported")
    if not api_key:
        raise AIUnavailable("not_configured")
    return cls(api_key, model)


def mask_key(api_key: str | None) -> str:
    """Display form of a key: never more than the last four characters."""
    if not api_key:
        return ""
    return "•" * 12 + (api_key[-4:] if len(api_key) >= 12 else "")
