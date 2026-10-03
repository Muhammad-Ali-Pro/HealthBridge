"""Thin OpenAI wrapper: JSON-only chat completion. Model comes from OPENAI_MODEL (never hard-coded)."""

import json

from core.config import settings


class LLMUnavailable(RuntimeError):
    pass


def available() -> bool:
    return settings.llm_available


def complete_json(system: str, user: str) -> dict:
    """Return the model's JSON object. Raises LLMUnavailable on any configuration/API/parse problem."""
    if not settings.llm_available:
        raise LLMUnavailable("AI is not configured")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, timeout=45, max_retries=1)
        response = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return json.loads(response.choices[0].message.content or "{}")
    except Exception as exc:  # network, auth, quota, malformed JSON — all mean "unavailable" for the UI
        raise LLMUnavailable(str(exc)[:200]) from exc
