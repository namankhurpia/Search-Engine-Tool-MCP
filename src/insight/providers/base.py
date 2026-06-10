"""Abstract SearchProvider interface — all adapters implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import SourceResult


class SearchProvider(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        max_results: int,
        recency: str | None = None,
        domain_filter: list[str] | None = None,
    ) -> list[SourceResult]:
        ...

    @abstractmethod
    async def synth(
        self,
        query: str,
        *,
        system_prompt: str,
        domain_filter: list[str] | None = None,
    ) -> tuple[str, list[SourceResult]]:
        ...

    async def aclose(self) -> None:
        """Override to release resources (HTTP clients, etc.)."""
