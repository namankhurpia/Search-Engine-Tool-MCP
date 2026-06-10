"""Mock provider for tests and offline development — no API key needed."""
from __future__ import annotations

from ..models import SourceResult
from .base import SearchProvider


class MockProvider(SearchProvider):
    async def search(
        self,
        query: str,
        *,
        max_results: int,
        recency: str | None = None,
        domain_filter: list[str] | None = None,
    ) -> list[SourceResult]:
        return [
            SourceResult(
                title=f"Mock result {i+1} for: {query}",
                url=f"https://example.com/{i+1}",
                snippet=f"This is mock snippet {i+1} about {query}.",
            )
            for i in range(min(max_results, 5))
        ]

    async def synth(
        self,
        query: str,
        *,
        system_prompt: str,
        domain_filter: list[str] | None = None,
    ) -> tuple[str, list[SourceResult]]:
        answer = f"Mock synthesized answer for: {query}"
        sources = [
            SourceResult(
                title=f"Source {i+1}",
                url=f"https://example.com/source/{i+1}",
            )
            for i in range(3)
        ]
        return answer, sources

    async def aclose(self) -> None:
        pass
