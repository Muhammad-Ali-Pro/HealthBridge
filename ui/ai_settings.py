"""Bring Your Own AI Key (BYOK) — demo only.

The tester's Gemini key is held ONLY in this browser session's `st.session_state` (server memory, one session).
It is never written to the database, files, logs, audit entries or URLs, never cached across sessions and never
displayed beyond its last four characters. "Clear API Key" removes it from the session.

Key precedence: key entered in this session > GEMINI_API_KEY (.env / environment / Streamlit secrets).
"""

from __future__ import annotations

import streamlit as st

from agents.providers import (
    DEFAULT_GEMINI_MODEL,
    FUTURE_PROVIDERS,
    GEMINI_MODELS,
    PROVIDERS,
    REASONS,
    AIProvider,
    AIUnavailable,
    ConnectionResult,
    build_provider,
    mask_key,
)
from core.config import ROOT_DIR, settings
from ui.components import alert_card, badge_html, card, esc, html

STATE = "_hb_byok"          # {"provider", "model", "key", "verified"} — session memory only
ss = st.session_state


def _state() -> dict:
    if STATE not in ss:
        ss[STATE] = {"provider": settings.ai_provider if settings.ai_provider in PROVIDERS else "gemini",
                     "model": settings.gemini_model or DEFAULT_GEMINI_MODEL, "key": None, "verified": False}
    return ss[STATE]


def _env_key() -> str | None:
    """Developer configuration: .env / environment, then Streamlit secrets (only if a secrets file exists)."""
    if settings.gemini_api_key:
        return settings.gemini_api_key
    if any(p.exists() for p in (ROOT_DIR / ".streamlit" / "secrets.toml",)):
        try:
            return st.secrets.get("GEMINI_API_KEY") or None
        except Exception:  # noqa: BLE001 — malformed secrets must not break the app
            return None
    return None


def status() -> dict:
    s = _state()
    source = "session" if s["key"] else ("environment" if _env_key() else None)
    return {"source": source if settings.ai_enabled else None, "verified": bool(s["key"]) and s["verified"],
            "model": s["model"], "provider": s["provider"], "label": PROVIDERS[s["provider"]].label,
            "masked": mask_key(s["key"] or _env_key())}


def active_provider() -> AIProvider | None:
    """The provider for this session, or None (→ labelled demo response). Built per call; never cached globally."""
    if not settings.ai_enabled:
        return None
    s = _state()
    key = s["key"] or _env_key()
    if not key:
        return None
    try:
        return build_provider(s["provider"], key, s["model"])
    except AIUnavailable:
        return None


def connect(provider: str, model: str, api_key: str | None) -> ConnectionResult:
    """Validate → initialize the provider → minimal data-free test request. Stores the key only on success."""
    api_key = (api_key or "").strip() or None
    key = api_key or _env_key()          # nothing entered → test the developer-configured key, if any
    if not key:
        return ConnectionResult(False, "Enter your Gemini API key first.", model)
    try:
        result = build_provider(provider, key, model).test_connection()
    except AIUnavailable as exc:
        return ConnectionResult(False, str(exc), model)
    s = _state()
    s.update(provider=provider, model=model)
    if result.ok:
        if api_key:
            s["key"] = api_key
        s["verified"] = True
    return result


def clear() -> None:
    s = _state()
    s["key"], s["verified"] = None, False
    ss.pop("_hb_byok_result", None)


def status_badge() -> str:
    st_ = status()
    if st_["source"] is None:
        return badge_html("AI not connected", "neutral", "link_off")
    if st_["verified"] or st_["source"] == "environment":
        return badge_html(f"{st_['label']} · {st_['model']}", "violet", "auto_awesome")
    return badge_html("AI key not verified", "amber", "warning")


def config_section(key: str) -> None:
    """The AI Configuration card: provider, model, password-style key, Connect & Test, Clear API Key."""
    st_ = status()
    with card(f"{key}_aicfg"):
        html('<div style="font-weight:800;font-size:1rem">AI Configuration · Bring Your Own AI Key</div>'
             '<div style="font-size:.8rem;color:var(--hb-muted);margin:.15rem 0 .6rem">Demo only. Your key stays in this '
             'browser session’s memory — never saved to HealthBridge’s database, logs or patient records, and never '
             'shared with other sessions.</div>')
        if "_hb_byok_result" in ss:
            ok, message = ss.pop("_hb_byok_result")
            alert_card("✓ Gemini connected successfully." if ok else message, tone="success" if ok else "danger",
                       icon_name="check_circle" if ok else "error")
        options = list(PROVIDERS) + list(FUTURE_PROVIDERS)
        labels = {k: v.label for k, v in PROVIDERS.items()} | FUTURE_PROVIDERS
        provider = st.selectbox("AI Provider", options, index=options.index(st_["provider"]),
                                format_func=labels.__getitem__, key=f"{key}_ai_provider")
        if provider not in PROVIDERS:
            alert_card(REASONS["unsupported"], "Phase 2 implements Google Gemini only. OpenAI can be added later "
                       "without changing the agents.", "info", "info")
            return

        if st_["source"] == "session" and st_["verified"]:
            alert_card("✓ AI provider connected", f"{esc(st_['label'])} · <b>Active model:</b> {esc(st_['model'])} · "
                       f"Key {esc(st_['masked'])}", "success", body_html=True)
            st.button("Clear API Key", key=f"{key}_ai_clear", icon=":material/key_off:", on_click=clear)
            return
        if st_["source"] == "environment":
            html(f'<div style="font-size:.82rem;margin-bottom:.4rem">{badge_html("Developer key from GEMINI_API_KEY", "blue", "settings")} '
                 f'<b>Active model:</b> {esc(st_["model"])} — a key entered below takes precedence for this session.</div>')

        models = list(GEMINI_MODELS) if st_["model"] in GEMINI_MODELS else [st_["model"], *GEMINI_MODELS]
        with st.form(f"{key}_ai_form", clear_on_submit=True, border=False):
            model = st.selectbox("Gemini model", models, index=models.index(st_["model"]), key=f"{key}_ai_model",
                                 help="Free-tier Gemini API models. Default: gemini-3.8-flash.")
            api_key = st.text_input("Gemini API Key", type="password", key=f"{key}_ai_key",
                                    placeholder="Paste your own key from Google AI Studio", autocomplete="off")
            submitted = st.form_submit_button("Connect & Test", icon=":material/power:", type="primary")
        st.caption("Get a free key at aistudio.google.com → Get API key. HealthBridge never provides a shared key.")
        if submitted:
            with st.spinner("Testing connection…"):
                result = connect(provider, model, api_key)
            ss["_hb_byok_result"] = (result.ok, result.message)
            st.rerun()
