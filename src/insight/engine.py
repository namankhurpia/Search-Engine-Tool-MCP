"""Dispatch a validated request to the provider, with cache + pagination + safety."""
from __future__ import annotations

from .cache import TTLCache
from .config import Settings
from .models import (
    PAGINATED_MODES,
    RAW_MODES,
    SYNTH_MODES,
    InsightRequest,
    InsightResponse,
    InsightType,
    SourceResult,
)
from .modes.handlers import shape_raw_query, synth_prompt
from .providers.base import SearchProvider
from .safety import domain_filter, filter_results


class Engine:
    def __init__(self, provider: SearchProvider, settings: Settings):
        self.provider = provider
        self.settings = settings
        self.cache = TTLCache(settings.cache_ttl_seconds) if settings.cache_enabled else None

    def _cache_key(self, req: InsightRequest) -> str:
        return f"{req.type.value}|{req.safety}|{req.query.strip().lower()}"

    async def run(self, req: InsightRequest) -> InsightResponse:
        if req.type in RAW_MODES:
            return await self._run_raw(req)
        if req.type in SYNTH_MODES:
            return await self._run_synth(req)
        raise ValueError(f"Unhandled type {req.type!r}")

    # --- raw modes --------------------------------------------------------
    async def _run_raw(self, req: InsightRequest) -> InsightResponse:
        key = self._cache_key(req)
        full: list[SourceResult] | None = self.cache.get(key) if self.cache else None

        if full is None:
            query, recency = shape_raw_query(req.type, req.query)
            dfilter = domain_filter(req.safety, self.settings.blocklist_domains())
            full = await self.provider.search(
                query,
                max_results=self.settings.max_results,
                recency=recency,
                domain_filter=dfilter or None,
            )
            full = filter_results(full, req.safety)
            if self.cache:
                self.cache.set(key, full)

        # Paginate over the cached full set.
        if req.type in PAGINATED_MODES:
            size = self.settings.page_size
            start = (req.page - 1) * size
            end = start + size
            page_items = full[start:end]
            has_more = end < len(full)
            page = req.page
        else:
            page_items = full
            has_more = False
            page = 1

        return InsightResponse(
            type=req.type,
            query=req.query,
            results=page_items,
            sources=[r.url for r in page_items if r.url],
            page=page,
            has_more=has_more,
            safety_applied=req.safety,
        )

    # --- synth modes ------------------------------------------------------
    async def _run_synth(self, req: InsightRequest) -> InsightResponse:
        key = self._cache_key(req)
        cached = self.cache.get(key) if self.cache else None

        if cached is None:
            dfilter = domain_filter(req.safety, self.settings.blocklist_domains())
            answer, sources = await self.provider.synth(
                req.query,
                system_prompt=synth_prompt(req.type),
                domain_filter=dfilter or None,
            )
            sources = filter_results(sources, req.safety)
            cached = (answer, sources)
            if self.cache:
                self.cache.set(key, cached)

        answer, sources = cached
        return InsightResponse(
            type=req.type,
            query=req.query,
            results=sources,
            answer=answer,
            sources=[r.url for r in sources if r.url],
            page=1,
            has_more=False,
            safety_applied=req.safety,
        )
