"""Authentication and shared-credential verification for the operator API.

Shared credential gate matching the console's contract:
- One shared secret (SYNC_API_PASSWORD or SYNC_CONSOLE_PASSWORD).
- Accepts `Authorization: Basic <base64(:password)>` or `Authorization: Bearer <password>`.
- Constant-time comparison via SHA-256 digest comparison.
- Fails closed: unauthenticated requests receive 401 Unauthorized with WWW-Authenticate header.
- Refuses off-loopback bind when no credential is configured.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

MINIMUM_CREDENTIAL_LENGTH = 12


def constant_time_match(offered: str, configured: str) -> bool:
    """Compare two credentials in constant time using fixed-width digests."""
    if not offered or not configured:
        return False
    offered_digest = hashlib.sha256(offered.encode("utf-8")).digest()
    configured_digest = hashlib.sha256(configured.encode("utf-8")).digest()
    return hmac.compare_digest(offered_digest, configured_digest)


def extract_credential(header: str | None) -> str | None:
    """Extract offered credential from Authorization header (Basic or Bearer)."""
    if not header:
        return None
    parts = header.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme == "bearer":
        return token
    if scheme == "basic":
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            # Format username:password (username is ignored)
            _, _, password = decoded.partition(":")
            return password
        except Exception:
            return None
    return None


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware protecting all routes behind a shared credential."""

    def __init__(self, app, *, password: str) -> None:
        super().__init__(app)
        self._password = password

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        auth_header = request.headers.get("Authorization")
        offered = extract_credential(auth_header)
        if not offered or not constant_time_match(offered, self._password):
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Sync API"'},
            )
        return await call_next(request)


def configured_api_password() -> str | None:
    """Read API password from environment (SYNC_API_PASSWORD or SYNC_CONSOLE_PASSWORD)."""
    val = os.environ.get("SYNC_API_PASSWORD") or os.environ.get("SYNC_CONSOLE_PASSWORD")
    if val and val.strip():
        return val.strip()
    return None


def validate_bind_security(host: str, password: str | None) -> None:
    """Refuse off-loopback bind if no credential is configured and insecure flag is unset."""
    is_loopback = host in ("127.0.0.1", "localhost", "::1")
    insecure = os.environ.get("SYNC_API_INSECURE") == "i-understand"
    if not is_loopback and not password and not insecure:
        raise ValueError(
            f"Refusing to bind {host} without authentication. Off-loopback, "
            "SYNC_API_PASSWORD or SYNC_CONSOLE_PASSWORD must be configured. "
            "If you understand the risk, set SYNC_API_INSECURE=i-understand."
        )
