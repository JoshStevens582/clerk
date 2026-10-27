"""Manager-only staff account administration (Atlas People parity)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.models import StaffUserRow
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import StaffAdminOut, StaffRole
from clerk.services.refresh_tokens import revoke_all_refresh_sessions

logger = logging.getLogger("clerk.staff_admin")

ROLE_MANAGER = "manager"
ROLE_STAFF = "staff"
VALID_ROLES = frozenset({ROLE_MANAGER, ROLE_STAFF})


class StaffAdminError(Exception):
    pass


class StaffAdminNotFoundError(StaffAdminError):
    pass


def staff_admin_out(row: StaffUserRow) -> StaffAdminOut:
    role: StaffRole = "manager" if row.role == ROLE_MANAGER else "staff"
    return StaffAdminOut(
        username=row.username,
        role=role,
        email=row.email,
        mfa_enabled=row.mfa_enabled_at is not None,
        active=row.active,
    )


def list_staff_admin_users(db_factory: sessionmaker[Session]) -> list[StaffAdminOut]:
    with db_factory() as session:
        rows = StaffRepository(session).list_all()
    return [staff_admin_out(row) for row in rows]


def set_staff_user_role(
    db_factory: sessionmaker[Session],
    *,
    actor_username: str,
    username: str,
    role: StaffRole,
) -> StaffAdminOut:
    if role not in VALID_ROLES:
        raise StaffAdminError("Role must be staff or manager.")
    target = username.strip().lower()
    if not target:
        raise StaffAdminNotFoundError("Account not found.")
    if actor_username.strip().lower() == target:
        raise StaffAdminError("You cannot change your own role.")
    db_role = ROLE_MANAGER if role == "manager" else ROLE_STAFF

    with db_factory() as session:
        repo = StaffRepository(session)
        user = repo.get_by_username(target)
        if user is None:
            raise StaffAdminNotFoundError("Account not found.")
        if user.role == ROLE_MANAGER and db_role == ROLE_STAFF:
            if repo.count_managers() <= 1:
                raise StaffAdminError("Cannot demote the last manager.")
        updated = repo.set_role(user.id, db_role)
        if updated is None:
            raise StaffAdminNotFoundError("Account not found.")
        session.commit()
        session.refresh(updated)
        result = staff_admin_out(updated)
    logger.info("manager set role actor=%s target=%s role=%s", actor_username, target, role)
    return result


def set_staff_user_active(
    db_factory: sessionmaker[Session],
    *,
    actor_username: str,
    username: str,
    active: bool,
) -> StaffAdminOut:
    target = username.strip().lower()
    if not target:
        raise StaffAdminNotFoundError("Account not found.")
    if not active and actor_username.strip().lower() == target:
        raise StaffAdminError("You cannot disable your own account.")

    revoke_user_id: int | None = None
    with db_factory() as session:
        repo = StaffRepository(session)
        user = repo.get_by_username(target)
        if user is None:
            raise StaffAdminNotFoundError("Account not found.")
        if not active and user.role == ROLE_MANAGER and repo.count_managers() <= 1:
            raise StaffAdminError("Cannot disable the last manager.")
        updated = repo.set_active(user.id, active)
        if updated is None:
            raise StaffAdminNotFoundError("Account not found.")
        session.commit()
        session.refresh(updated)
        if not active:
            revoke_user_id = updated.id
        result = staff_admin_out(updated)

    if revoke_user_id is not None:
        revoke_all_refresh_sessions(db_factory, user_id=revoke_user_id)
    logger.info(
        "manager set active actor=%s target=%s active=%s",
        actor_username,
        target,
        active,
    )
    return result
