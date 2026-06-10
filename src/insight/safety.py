"""Safety filtering — domain blocklist + light content filter (v1)."""
from __future__ import annotations

from .models import SourceResult

# Terms that indicate low-quality / spam results when safety is on.
_FLAGGED_TERMS = {"casino", "porn", "xxx", "gambling", "torrent"}


def domain_filter(safety: bool, blocklist: list[str]) -> list[str] | None:
    """Return a domain-exclusion list suitable for the provider, or None."""
    if not safety:
        return None
    return blocklist if blocklist else None


def filter_results(results: list[SourceResult], safety: bool) -> list[SourceResult]:
    """Post-filter results when safety is on."""
    if not safety:
        return results
    filtered = []
    for r in results:
        text = f"{r.title} {r.snippet} {r.url}".lower()
        if any(term in text for term in _FLAGGED_TERMS):
            continue
        filtered.append(r)
    return filtered
