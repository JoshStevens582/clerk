"""Refresh tokens: short access JWT + revocable refresh rows."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.models import StaffUserRow
from clerk.repositories.refresh_repo import RefreshRepository, normalize_expiry
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import StaffRole
from clerk.services.jwt_tokens import issue_access_token

REFRESH_TOKEN_BYTES = 32


class RefreshError(Exception):
    pass


@dataclass(frozen=True)
class SessionPair:
    access_token: str
    refresh_token: str
    username: str
    role: StaffRole


def hash_refresh_token(raw: str) -> str:
    normalized = raw.strip()
    if not normalized:
        raise ValueError("Refresh token is empty.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _new_raw_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def staff_role(row: StaffUserRow) -> StaffRole:
    return "manager" if row.role == "manager" else "staff"


def issue_session_pair(
    db_factory: sessionmaker[Session],
    settings: Settings,
    *,
    user: StaffUserRow,
    now: datetime | None = None,
) -> SessionPair:
    moment = now or datetime.now(UTC)
    raw = _new_raw_refresh_token()
    family_id = secrets.token_hex(16)
    expires_at = moment + timedelta(seconds=settings.refresh_token_ttl_seconds)
    with db_factory() as session:
        RefreshRepository(session).insert(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id,
            expires_at=expires_at,
        )
        session.commit()
    return SessionPair(
        access_token=issue_access_token(settings, user.username, now=moment),
        refresh_token=raw,
        username=user.username,
        role=staff_role(user),
    )


def rotate_refresh_token(
    db_factory: sessionmaker[Session],
    settings: Settings,
    *,
    raw_refresh_token: str,
    now: datetime | None = None,
) -> SessionPair:
    moment = now or datetime.now(UTC)
    token_hash = hash_refresh_token(raw_refresh_token)
    with db_factory() as session:
        repo = RefreshRepository(session)
        row = repo.find_by_hash(token_hash)
        if row is None:
            raise RefreshError("Refresh token is not valid.")
        if row.revoked_at is not None:
            repo.revoke_family(row.family_id, revoked_at=moment)
            session.commit()
            raise RefreshError("Refresh token was revoked. Sign in again.")
        expires_at = normalize_expiry(row.expires_at)
        if expires_at <= moment:
            repo.revoke(row.id, revoked_at=moment)
            session.commit()
            raise RefreshError("Refresh token expired. Sign in again.")
        user = StaffRepository(session).get_by_id(row.user_id)
        if user is None or not user.active:
            repo.revoke_family(row.family_id, revoked_at=moment)
            session.commit()
            raise RefreshError("This account is not available.")
        repo.revoke(row.id, revoked_at=moment)
        new_raw = _new_raw_refresh_token()
        new_expires = moment + timedelta(seconds=settings.refresh_token_ttl_seconds)
        username = user.username
        role = staff_role(user)
        repo.insert(
            user_id=user.id,
            token_hash=hash_refresh_token(new_raw),
            family_id=row.family_id,
            expires_at=new_expires,
        )
        session.commit()
    return SessionPair(
        access_token=issue_access_token(settings, username, now=moment),
        refresh_token=new_raw,
        username=username,
        role=role,
    )


def revoke_refresh_token(
    db_factory: sessionmaker[Session],
    *,
    raw_refresh_token: str,
    now: datetime | None = None,
) -> None:
    moment = now or datetime.now(UTC)
    token_hash = hash_refresh_token(raw_refresh_token)
    with db_factory() as session:
        repo = RefreshRepository(session)
        row = repo.find_by_hash(token_hash)
        if row is None:
            return
        if row.revoked_at is None:
            repo.revoke(row.id, revoked_at=moment)
        session.commit()


def revoke_all_refresh_sessions(
    db_factory: sessionmaker[Session],
    *,
    user_id: int,
    now: datetime | None = None,
) -> None:
    moment = now or datetime.now(UTC)
    with db_factory() as session:
        RefreshRepository(session).revoke_all_for_user(user_id, revoked_at=moment)
        session.commit()
