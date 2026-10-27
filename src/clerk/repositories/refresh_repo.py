from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from clerk.repositories.models import RefreshSessionRow


class RefreshRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(
        self,
        *,
        user_id: int,
        token_hash: str,
        family_id: str,
        expires_at: datetime,
    ) -> RefreshSessionRow:
        row = RefreshSessionRow(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def find_by_hash(self, token_hash: str) -> RefreshSessionRow | None:
        stmt = select(RefreshSessionRow).where(RefreshSessionRow.token_hash == token_hash)
        return self._session.scalar(stmt)

    def revoke(self, session_id: str, *, revoked_at: datetime) -> None:
        self._session.execute(
            update(RefreshSessionRow)
            .where(RefreshSessionRow.id == session_id)
            .values(revoked_at=revoked_at)
        )

    def revoke_family(self, family_id: str, *, revoked_at: datetime) -> None:
        self._session.execute(
            update(RefreshSessionRow)
            .where(RefreshSessionRow.family_id == family_id, RefreshSessionRow.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )

    def revoke_all_for_user(self, user_id: int, *, revoked_at: datetime) -> None:
        self._session.execute(
            update(RefreshSessionRow)
            .where(RefreshSessionRow.user_id == user_id, RefreshSessionRow.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )


def normalize_expiry(expires_at: datetime) -> datetime:
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=UTC)
    return expires_at
