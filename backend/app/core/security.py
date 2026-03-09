from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings


class AuthError(HTTPException):
    def __init__(self, detail: str = "Invalid authentication token") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(message: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(signature)


def create_access_token(subject: str, expires_delta: timedelta | None = None, extra: dict[str, Any] | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    expire_delta = expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    expire_at = datetime.now(UTC) + expire_delta

    payload: dict[str, Any] = {"sub": subject, "exp": int(expire_at.timestamp()), "iat": int(datetime.now(UTC).timestamp())}
    if extra:
        payload.update(extra)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _sign(signing_input, settings.jwt_secret)
    return f"{header_b64}.{payload_b64}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Malformed token")

    header_b64, payload_b64, signature = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_signature = _sign(signing_input, settings.jwt_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthError("Token signature mismatch")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:  # pragma: no cover
        raise AuthError("Token payload decode failed") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise AuthError("Token missing exp")
    if datetime.now(UTC).timestamp() > exp:
        raise AuthError("Token expired")

    return payload


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthError("Missing Authorization header")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise AuthError("Authorization header must be Bearer token")
    return authorization[len(prefix) :].strip()
