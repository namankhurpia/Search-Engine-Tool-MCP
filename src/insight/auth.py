"""Auth dependency — validates Bearer token against the CSV keystore."""
from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .errors import InsightError
from .keystore import KeyStore

_bearer = HTTPBearer(auto_error=False)

# Singleton keystore, path configured via settings at startup.
_keystore: KeyStore | None = None


def init_keystore(path: str) -> KeyStore:
    global _keystore
    _keystore = KeyStore(path)
    return _keystore


def get_keystore() -> KeyStore:
    if _keystore is None:
        raise InsightError("AUTH_NOT_CONFIGURED", "Keystore not initialized.", 500)
    return _keystore


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency that enforces a valid API key.

    If auth is disabled in settings, returns 'anonymous' without checking.
    Returns the key name on success; raises 401/403 on failure.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        return "anonymous"

    if credentials is None:
        raise InsightError(
            "AUTH_REQUIRED",
            "Missing Authorization header. Use: Authorization: Bearer <your-api-key>",
            status_code=401,
        )

    ks = get_keystore()
    key_name = ks.validate_key(credentials.credentials)
    if key_name is None:
        raise InsightError(
            "INVALID_API_KEY",
            "The provided API key is invalid or has been revoked.",
            status_code=403,
        )
    return key_name
