"""App settings loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Resolve .env relative to this file's location (src/insight/config.py)
# so it works regardless of uvicorn's working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


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
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
