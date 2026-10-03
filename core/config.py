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
    openai_api_key: str | None
    openai_model: str | None
    ai_enabled: bool

    @property
    def llm_available(self) -> bool:
        """True only when AI is enabled and both key and model are configured."""
        return self.ai_enabled and bool(self.openai_api_key) and bool(self.openai_model)


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'healthbridge.db').as_posix()}"),
        upload_dir=Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads"))),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL") or None,
        ai_enabled=_truthy(os.getenv("AI_ENABLED"), default=True),
    )


settings = load_settings()
