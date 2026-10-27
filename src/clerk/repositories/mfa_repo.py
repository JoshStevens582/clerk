from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import delete, or_, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from clerk.repositories.models import MfaRecoveryCodeRow, StaffUserRow


def _one_row_changed(result: object) -> bool:
    return cast(CursorResult[Any], result).rowcount == 1


class MfaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_pending_secret(self, user: StaffUserRow, encrypted_secret: str) -> None:
        self._session.execute(
            delete(MfaRecoveryCodeRow).where(MfaRecoveryCodeRow.user_id == user.id)
        )
        user.mfa_secret = encrypted_secret
        user.mfa_enabled_at = None
        user.mfa_last_step = None

    def confirm(
        self,
        user: StaffUserRow,
        *,
        enabled_at: datetime,
        last_step: int,
        code_hashes: list[str],
    ) -> bool:
        result = self._session.execute(
            update(StaffUserRow)
            .where(StaffUserRow.id == user.id, StaffUserRow.mfa_enabled_at.is_(None))
            .values(mfa_enabled_at=enabled_at, mfa_last_step=last_step)
            .execution_options(synchronize_session=False)
        )
        if not _one_row_changed(result):
            return False
        self._session.execute(
            delete(MfaRecoveryCodeRow).where(MfaRecoveryCodeRow.user_id == user.id)
        )
        for code_hash in code_hashes:
            self._session.add(
                MfaRecoveryCodeRow(
                    id=str(uuid4()),
                    user_id=user.id,
                    code_hash=code_hash,
                )
            )
        user.mfa_enabled_at = enabled_at
        user.mfa_last_step = last_step
        return True

    def clear(self, user: StaffUserRow) -> None:
        self._session.execute(
            delete(MfaRecoveryCodeRow).where(MfaRecoveryCodeRow.user_id == user.id)
        )
        user.mfa_secret = None
        user.mfa_enabled_at = None
        user.mfa_last_step = None

    def claim_totp_step(self, user_id: int, step: int) -> bool:
        result = self._session.execute(
            update(StaffUserRow)
            .where(StaffUserRow.id == user_id)
            .where(or_(StaffUserRow.mfa_last_step.is_(None), StaffUserRow.mfa_last_step < step))
            .values(mfa_last_step=step)
            .execution_options(synchronize_session=False)
        )
        return _one_row_changed(result)

    def replace_recovery_codes(self, user_id: int, code_hashes: list[str]) -> None:
        self._session.execute(
            delete(MfaRecoveryCodeRow).where(MfaRecoveryCodeRow.user_id == user_id)
        )
        for code_hash in code_hashes:
            self._session.add(
                MfaRecoveryCodeRow(
                    id=str(uuid4()),
                    user_id=user_id,
                    code_hash=code_hash,
                )
            )

    def consume_recovery_code(
        self,
        user_id: int,
        code_hash: str,
        *,
        used_at: datetime,
    ) -> bool:
        result = self._session.execute(
            update(MfaRecoveryCodeRow)
            .where(
                MfaRecoveryCodeRow.user_id == user_id,
                MfaRecoveryCodeRow.code_hash == code_hash,
                MfaRecoveryCodeRow.used_at.is_(None),
            )
            .values(used_at=used_at)
            .execution_options(synchronize_session=False)
        )
        return _one_row_changed(result)
