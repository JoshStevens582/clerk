"""Signed JWT access and MFA challenge tokens (Atlas-style)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from clerk.config import Settings

JWT_ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_MFA = "mfa"


def issue_access_token(
    settings: Settings,
    username: str,
    *,
    now: datetime | None = None,
) -> str:
    moment = now or datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": moment,
        "exp": moment + timedelta(seconds=settings.access_token_ttl_seconds),
        "typ": TOKEN_TYPE_ACCESS,
    }
    return jwt.encode(payload, settings.clerk_auth_secret, algorithm=JWT_ALGORITHM)


def issue_mfa_challenge_token(settings: Settings, username: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(seconds=settings.mfa_challenge_ttl_seconds),
        "typ": TOKEN_TYPE_MFA,
    }
    return jwt.encode(payload, settings.clerk_auth_secret, algorithm=JWT_ALGORITHM)


def _decode_token(settings: Settings, token: str) -> dict[str, object] | None:
    if not token.strip() or not settings.clerk_auth_secret:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.clerk_auth_secret,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.InvalidTokenError:
        return None
    if not isinstance(payload, dict):
        return None
    decoded: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            return None
        decoded[key] = value
    return decoded


def _subject(payload: dict[str, object]) -> str | None:
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject


def verify_access_token(settings: Settings, token: str) -> str | None:
    payload = _decode_token(settings, token)
    if payload is None:
        return None
    token_type = payload.get("typ")
    if token_type not in (None, TOKEN_TYPE_ACCESS):
        return None
    return _subject(payload)


def verify_mfa_challenge_token(settings: Settings, token: str) -> str | None:
    payload = _decode_token(settings, token)
    if payload is None:
        return None
    if payload.get("typ") != TOKEN_TYPE_MFA:
        return None
    return _subject(payload)
