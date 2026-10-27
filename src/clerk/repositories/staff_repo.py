from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clerk.repositories.models import StaffUserRow
from clerk.schemas.staff import StaffRole


class StaffRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_users(self) -> int:
        stmt = select(func.count()).select_from(StaffUserRow)
        return int(self._session.scalar(stmt) or 0)

    def get_by_username(self, username: str) -> StaffUserRow | None:
        normalized = username.strip().lower()
        stmt = select(StaffUserRow).where(StaffUserRow.username == normalized)
        return self._session.scalar(stmt)

    def get_by_id(self, user_id: int) -> StaffUserRow | None:
        stmt = select(StaffUserRow).where(StaffUserRow.id == user_id)
        return self._session.scalar(stmt)

    def get_by_email(self, email: str) -> StaffUserRow | None:
        normalized = email.strip().lower()
        stmt = select(StaffUserRow).where(StaffUserRow.email == normalized)
        return self._session.scalar(stmt)

    def list_active(self) -> list[StaffUserRow]:
        stmt = (
            select(StaffUserRow)
            .where(StaffUserRow.active.is_(True))
            .order_by(StaffUserRow.username)
        )
        return list(self._session.scalars(stmt))

    def list_all(self) -> list[StaffUserRow]:
        stmt = select(StaffUserRow).order_by(StaffUserRow.username)
        return list(self._session.scalars(stmt))

    def count_managers(self) -> int:
        stmt = (
            select(func.count())
            .select_from(StaffUserRow)
            .where(StaffUserRow.role == "manager")
        )
        return int(self._session.scalar(stmt) or 0)

    def set_role(self, user_id: int, role: str) -> StaffUserRow | None:
        row = self.get_by_id(user_id)
        if row is None:
            return None
        row.role = role
        self._session.flush()
        return row

    def set_active(self, user_id: int, active: bool) -> StaffUserRow | None:
        row = self.get_by_id(user_id)
        if row is None:
            return None
        row.active = active
        self._session.flush()
        return row

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        role: StaffRole,
        display_name: str | None,
        email: str | None = None,
    ) -> StaffUserRow:
        normalized_email = email.strip().lower() if email and email.strip() else None
        row = StaffUserRow(
            username=username.strip().lower(),
            password_hash=password_hash,
            role=role,
            display_name=display_name,
            email=normalized_email,
            active=True,
        )
        self._session.add(row)
        self._session.flush()
        return row
