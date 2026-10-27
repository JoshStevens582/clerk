from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from clerk.repositories.models import PasswordResetTokenRow


class PasswordResetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_token_for_user(
        self,
        user_id: int,
        *,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        self._session.execute(
            delete(PasswordResetTokenRow).where(PasswordResetTokenRow.user_id == user_id)
        )
        self._session.add(
            PasswordResetTokenRow(
                id=str(uuid4()),
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

    def find_valid_token(self, token_hash: str, *, now: datetime) -> PasswordResetTokenRow | None:
        stmt = select(PasswordResetTokenRow).where(
            PasswordResetTokenRow.token_hash == token_hash
        )
        row = self._session.scalar(stmt)
        if row is None:
            return None
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            return None
        return row

    def delete_token(self, token_id: str) -> None:
        self._session.execute(
            delete(PasswordResetTokenRow).where(PasswordResetTokenRow.id == token_id)
        )
