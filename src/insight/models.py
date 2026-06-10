"""Request / response schemas and the InsightType enum."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InsightType(str, Enum):
    search = "search"
    news = "news"
    local = "local"
    deals = "deals"
    answer = "answer"
    recommend = "recommend"
    compare = "compare"
    reviews = "reviews"
    alternatives = "alternatives"


# --- mode groupings used by Engine -------------------------------------------

RAW_MODES = {InsightType.search, InsightType.news, InsightType.local, InsightType.deals}
SYNTH_MODES = {
    InsightType.answer,
    InsightType.recommend,
    InsightType.compare,
    InsightType.reviews,
    InsightType.alternatives,
}
PAGINATED_MODES = {InsightType.search, InsightType.news, InsightType.local, InsightType.reviews}


# --- data models -------------------------------------------------------------

class SourceResult(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    date: Optional[str] = None
    last_updated: Optional[str] = None


class InsightRequest(BaseModel):
    type: InsightType
    query: str = Field(..., min_length=1, max_length=2000)
    safety: bool = True
    page: int = Field(default=1, ge=1)


class InsightResponse(BaseModel):
    type: InsightType
    query: str
    results: list[SourceResult] = []
    answer: Optional[str] = None
    sources: list[str] = []
    page: int = 1
    has_more: bool = False
    safety_applied: bool = True
