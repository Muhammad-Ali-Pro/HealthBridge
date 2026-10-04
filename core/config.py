"""Runtime configuration, read from environment variables / .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"

load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str
    upload_dir: Path
    ai_provider: str
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    ai_enabled: bool = True

    @property
    def env_ai_configured(self) -> bool:
        """True when a developer configured a key in .env / the environment (a UI key still takes precedence)."""
        return self.ai_enabled and self.ai_provider == "gemini" and bool(self.gemini_api_key)

    def __repr__(self) -> str:  # never print the key
        return (f"Settings(database_url={self.database_url!r}, ai_provider={self.ai_provider!r}, "
                f"gemini_model={self.gemini_model!r}, gemini_api_key={'set' if self.gemini_api_key else 'unset'}, "
                f"ai_enabled={self.ai_enabled})")


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'healthbridge.db').as_posix()}"),
        upload_dir=Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads"))),
        ai_provider=(os.getenv("AI_PROVIDER") or "gemini").strip().lower(),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL") or None,
        ai_enabled=_truthy(os.getenv("AI_ENABLED"), default=True),
    )


settings = load_settings()
