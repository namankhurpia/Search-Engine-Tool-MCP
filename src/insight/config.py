"""App settings loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Find .env: check ENV_FILE env var first, then common locations.
def _find_env_file() -> str:
    import os
    explicit = os.environ.get("ENV_FILE")
    if explicit and Path(explicit).exists():
        return explicit
    candidates = [
        Path.cwd() / ".env",                                    # working directory
        Path(__file__).resolve().parent.parent.parent / ".env",  # relative to source
        Path("/app/.env"),                                       # Docker default
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ".env"  # fallback

_ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    # Provider
    provider: str = "perplexity"

    # Perplexity
    perplexity_api_key: Optional[str] = None
    perplexity_synth_model: str = "sonar"
    perplexity_search_context: str = "low"

    # Engine behaviour
    max_results: int = 20
    page_size: int = 10
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

    # Auth
    auth_enabled: bool = True
    keys_file: str = "keys.csv"

    # Safety
    safety_blocklist: str = ""  # comma-separated domains

    def blocklist_domains(self) -> list[str]:
        if not self.safety_blocklist.strip():
            return []
        return [d.strip() for d in self.safety_blocklist.split(",") if d.strip()]

    model_config = {
        "env_prefix": "INSIGHT_",
        "env_file": _ENV_FILE,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
