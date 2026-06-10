"""Perplexity adapter.

Two endpoints, two cost profiles (plan.md S5):
  - POST /search           -> raw ranked results, flat $5 / 1k requests
  - POST /chat/completions -> Sonar synthesis, $1/1M tokens + low-context request fee

Schema for /search confirmed from the official OpenAPI spec at
https://docs.perplexity.ai/api-reference/search-post
"""
from __future__ import annotations

import httpx

from ..errors import provider_error, provider_unconfigured
from ..models import SourceResult
from .base import SearchProvider


class PerplexityProvider(SearchProvider):
    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.perplexity.ai",
        synth_model: str = "sonar",
        search_context: str = "low",
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.synth_model = synth_model
        self.search_context = search_context
        self._client = httpx.AsyncClient(timeout=timeout)

    def _headers(self) -> dict:
        if not self.api_key:
            raise provider_unconfigured()
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            resp = await self._client.post(
                f"{self.base_url}{path}", headers=self._headers(), json=payload
            )
        except httpx.HTTPError as exc:
            raise provider_error(str(exc)) from exc
        if resp.status_code >= 400:
            raise provider_error(f"{resp.status_code} {resp.text[:300]}")
        return resp.json()

    # --- raw search -------------------------------------------------------
    async def search(
        self,
        query: str,
        *,
        max_results: int,
        recency: str | None = None,
        domain_filter: list[str] | None = None,
    ) -> list[SourceResult]:
        payload: dict = {
            "query": query,
            "max_results": max_results,
            "search_context_size": self.search_context,
        }
        if recency:
            payload["search_recency_filter"] = recency
        if domain_filter:
            payload["search_domain_filter"] = domain_filter

        data = await self._post("/search", payload)
        results = []
        for item in data.get("results", []):
            results.append(
                SourceResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    date=item.get("date"),
                    last_updated=item.get("last_updated"),
                )
            )
        return results

    # --- synthesis --------------------------------------------------------
    async def synth(
        self,
        query: str,
        *,
        system_prompt: str,
        domain_filter: list[str] | None = None,
    ) -> tuple[str, list[SourceResult]]:
        payload: dict = {
            "model": self.synth_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "web_search_options": {"search_context_size": self.search_context},
        }
        if domain_filter:
            payload["search_domain_filter"] = domain_filter

        data = await self._post("/chat/completions", payload)
        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise provider_error(f"unexpected response shape: {exc}") from exc

        return answer, _extract_sources(data)

    async def aclose(self) -> None:
        await self._client.aclose()


def _extract_sources(data: dict) -> list[SourceResult]:
    """Sonar has used both `search_results` (objects) and `citations` (urls)
    over time; handle either so the adapter survives minor API changes."""
    sources: list[SourceResult] = []

    for item in data.get("search_results") or []:
        if isinstance(item, dict) and item.get("url"):
            sources.append(
                SourceResult(
                    title=item.get("title", ""),
                    url=item["url"],
                    date=item.get("date"),
                )
            )

    if not sources:
        for url in data.get("citations") or []:
            if isinstance(url, str):
                sources.append(SourceResult(url=url))

    return sources
