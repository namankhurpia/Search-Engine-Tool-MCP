"""FastAPI application — exposes POST /insight for agent callers (plan.md S3)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .auth import init_keystore, require_api_key
from .config import get_settings
from .engine import Engine
from .errors import InsightError
from .models import InsightRequest, InsightResponse, InsightType
from .providers import build_provider

logger = logging.getLogger("insight")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auth_enabled:
        init_keystore(settings.keys_file)
    provider = build_provider(settings)
    app.state.engine = Engine(provider, settings)
    try:
        yield
    finally:
        await provider.aclose()


app = FastAPI(
    title="Insight Engine",
    version="0.2.0",
    description="One web-research endpoint for LLM agents. POST /insight with {type, query}.",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request with method, path, client IP, and headers."""
    client = request.client.host if request.client else "unknown"
    headers = dict(request.headers)
    # Mask the auth token for security
    if "authorization" in headers:
        token = headers["authorization"]
        if len(token) > 20:
            headers["authorization"] = token[:15] + "..." + token[-4:]
    logger.info(
        "REQUEST %s %s from=%s headers=%s",
        request.method,
        request.url.path,
        client,
        headers,
    )
    response = await call_next(request)
    logger.info(
        "RESPONSE %s %s status=%d",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.exception_handler(InsightError)
async def _insight_error_handler(_: Request, exc: InsightError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_body())


@app.exception_handler(RequestValidationError)
async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    msg = first.get("msg", "Invalid request.")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_REQUEST", "message": f"{loc}: {msg}".strip(": ")}},
    )


# --- public endpoints (no auth) ---------------------------------------------

@app.get("/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "provider": s.provider,
        "synth_model": s.perplexity_synth_model,
        "cache": s.cache_enabled,
        "auth": s.auth_enabled,
    }


@app.get("/types")
async def types() -> dict:
    """Lets an agent discover the available actions at runtime."""
    return {"types": [t.value for t in InsightType]}


# --- protected endpoints -----------------------------------------------------

def _get_auth_dependency():
    """Returns the auth dependency if enabled, otherwise a no-op."""
    settings = get_settings()
    if settings.auth_enabled:
        return Depends(require_api_key)
    return Depends(lambda: "anonymous")


@app.post("/insight", response_model=InsightResponse)
async def insight(
    req: InsightRequest,
    request: Request,
    caller: str = Depends(require_api_key),
) -> InsightResponse:
    engine: Engine = request.app.state.engine
    return await engine.run(req)
