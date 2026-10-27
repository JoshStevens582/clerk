"""Forgot-password tokens and optional SMTP delivery (Atlas-style)."""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.password_reset_repo import PasswordResetRepository
from clerk.repositories.staff_repo import StaffRepository
from clerk.services.smtp import send_plain_email
from clerk.services.staff_auth import hash_password

logger = logging.getLogger("clerk.password_reset")

MIN_PASSWORD_LENGTH = 8
FORGOT_PASSWORD_MESSAGE = (
    "If an account exists with a reset email on file, password reset instructions were sent."
)


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class ForgotPasswordResult:
    message: str
    dev_reset_token: str | None


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def reset_link(settings: Settings, raw_token: str) -> str:
    base = settings.app_public_url.strip().rstrip("/")
    if not base:
        base = "http://localhost:5175"
    return f"{base}/?reset_token={raw_token}"


async def request_password_reset(
    db_factory: sessionmaker[Session],
    settings: Settings,
    *,
    username: str,
) -> ForgotPasswordResult:
    username = username.strip()
    with db_factory() as session:
        user = StaffRepository(session).get_by_username(username)

    if user is None or not user.email:
        return ForgotPasswordResult(message=FORGOT_PASSWORD_MESSAGE, dev_reset_token=None)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.password_reset_ttl_seconds)

    with db_factory() as session:
        PasswordResetRepository(session).replace_token_for_user(
            user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.commit()

    link = reset_link(settings, raw_token)
    sent = await send_plain_email(
        settings,
        to_address=user.email,
        subject="Clerk password reset",
        body=(
            "Use this link to choose a new Clerk password. It expires in one hour.\n\n"
            f"{link}\n\n"
            "If you did not request this, you can ignore this email."
        ),
    )
    if not sent:
        logger.warning(
            "password reset email not sent username=%s smtp_configured=%s",
            user.username,
            bool(settings.smtp_host),
        )

    dev_token: str | None = None
    if settings.password_reset_expose_token_in_response and not sent:
        dev_token = raw_token

    return ForgotPasswordResult(message=FORGOT_PASSWORD_MESSAGE, dev_reset_token=dev_token)


def reset_password_with_token(
    db_factory: sessionmaker[Session],
    *,
    raw_token: str,
    new_password: str,
) -> str:
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    token_hash = hash_reset_token(raw_token.strip())
    now = datetime.now(UTC)
    with db_factory() as session:
        reset_repo = PasswordResetRepository(session)
        row = reset_repo.find_valid_token(token_hash, now=now)
        if row is None:
            raise AuthError("Invalid or expired reset token.")
        user = StaffRepository(session).get_by_id(row.user_id)
        if user is None:
            raise AuthError("Invalid or expired reset token.")
        user.password_hash = hash_password(new_password)
        reset_repo.delete_token(row.id)
        session.commit()
        username = user.username
    return username
