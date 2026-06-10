"""Per-mode query shaping and Sonar system prompts."""
from __future__ import annotations

from ..models import InsightType


def shape_raw_query(mode: InsightType, query: str) -> tuple[str, str | None]:
    """Return (rewritten_query, recency_filter | None) for raw-search modes."""
    if mode == InsightType.news:
        return query, "week"
    if mode == InsightType.local:
        return f"{query} near me", None
    if mode == InsightType.deals:
        return f"{query} price buy", None
    # search (default)
    return query, None


_SYNTH_PROMPTS: dict[InsightType, str] = {
    InsightType.answer: (
        "You are a research assistant. Answer the user's question concisely with "
        "citations. Use numbered references [1], [2], etc."
    ),
    InsightType.recommend: (
        "You are a product recommendation expert. Return a ranked list of the best "
        "options with a short reason, approximate price, and a link for each. "
        "Cite your sources."
    ),
    InsightType.compare: (
        "You are a comparison analyst. Build a side-by-side comparison of the items "
        "the user asks about. End with a short verdict. Cite sources."
    ),
    InsightType.reviews: (
        "You are a review aggregator. Summarise sentiment, list pros and cons, and "
        "include representative short quotes (paraphrased, with attribution). "
        "Cite sources."
    ),
    InsightType.alternatives: (
        "You are a market analyst. List alternatives/competitors to the item the user "
        "names, with a one-line differentiator for each. Cite sources."
    ),
}


def synth_prompt(mode: InsightType) -> str:
    return _SYNTH_PROMPTS.get(mode, _SYNTH_PROMPTS[InsightType.answer])
