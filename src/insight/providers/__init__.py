"""Provider registry — returns a configured SearchProvider from settings."""
from __future__ import annotations

from ..config import Settings
from .base import SearchProvider


def build_provider(settings: Settings) -> SearchProvider:
    name = settings.provider.lower()
    if name == "perplexity":
        from .perplexity import PerplexityProvider

        return PerplexityProvider(
            api_key=settings.perplexity_api_key,
            synth_model=settings.perplexity_synth_model,
            search_context=settings.perplexity_search_context,
        )
    if name == "mock":
        from .mock import MockProvider

        return MockProvider()
    raise ValueError(f"Unknown provider: {name!r}. Use 'perplexity' or 'mock'.")
