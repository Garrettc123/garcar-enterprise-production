"""Shared-secret API key check for the billing services (hardening audit, Oct 2026).

Callers send the key in the ``X-API-Key`` header (or ``Authorization: Bearer <key>``).
The expected key is read from an env var at request time, so rotating it only needs
a restart. If the env var is missing or empty, every request is refused with 503
(fail closed): an unconfigured service must never be open.
"""
import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException


def _presented_key(x_api_key: Optional[str], authorization: Optional[str]) -> str:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def check_api_key(env_var: str, x_api_key: Optional[str], authorization: Optional[str]) -> None:
    expected = os.getenv(env_var, "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"Service locked: {env_var} is not configured")
    presented = _presented_key(x_api_key, authorization)
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key",
                            headers={"WWW-Authenticate": "Bearer"})


def api_key_dependency(env_var: str):
    """Return a FastAPI dependency that enforces the key stored in ``env_var``."""

    def _dep(x_api_key: Optional[str] = Header(default=None),
             authorization: Optional[str] = Header(default=None)) -> None:
        check_api_key(env_var, x_api_key, authorization)

    return _dep
