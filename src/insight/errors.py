"""Structured error types — always JSON, never free text."""
from __future__ import annotations


class InsightError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


# --- convenience constructors ------------------------------------------------

def provider_unconfigured() -> InsightError:
    return InsightError(
        "PROVIDER_UNCONFIGURED",
        "The search provider API key is not set. Check your .env file.",
        status_code=503,
    )


def provider_error(detail: str) -> InsightError:
    return InsightError(
        "PROVIDER_ERROR",
        f"Upstream provider returned an error: {detail}",
        status_code=502,
    )
