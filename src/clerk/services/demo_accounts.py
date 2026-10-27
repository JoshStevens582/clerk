"""Public demo desk accounts (isolated from live patient mail)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import StaffRole
from clerk.services.staff_auth import hash_password, parse_bootstrap_spec

logger = logging.getLogger("clerk.demo")

_DEMO_SPEC_SEP = "|"


def parse_demo_user_specs(raw: str) -> list[tuple[str, str, StaffRole]]:
    """Parse ``user:pass`` or ``user:pass:role`` entries separated by ``|``."""
    entries: list[tuple[str, str, StaffRole]] = []
    for chunk in raw.split(_DEMO_SPEC_SEP):
        piece = chunk.strip()
        if not piece:
            continue
        entries.extend(parse_bootstrap_spec(piece))
    return entries


def demo_usernames(settings: Settings) -> frozenset[str]:
    specs = parse_demo_user_specs(settings.clerk_demo_users)
    return frozenset(username for username, _, _ in specs)


def is_demo_staff(settings: Settings, username: str) -> bool:
    return username.strip().lower() in demo_usernames(settings)


def ensure_demo_staff_users(settings: Settings, db_factory: sessionmaker[Session]) -> None:
    specs = parse_demo_user_specs(settings.clerk_demo_users)
    if not specs:
        return
    admin_names = {
        name.strip().lower()
        for name in settings.clerk_admin_usernames.split(",")
        if name.strip()
    }
    with db_factory() as session:
        repo = StaffRepository(session)
        for username, password, role in specs:
            effective_role: StaffRole = "manager" if username in admin_names else role
            if effective_role == "manager":
                effective_role = "staff"
            row = repo.get_by_username(username)
            digest = hash_password(password)
            if row is None:
                repo.create_user(
                    username=username,
                    password_hash=digest,
                    role=effective_role,
                    display_name="Demo visitor",
                )
                logger.info("Created demo staff user username=%s", username)
            else:
                row.password_hash = digest
                row.active = True
                row.role = effective_role
                if row.mfa_enabled_at is not None:
                    row.mfa_enabled_at = None
                    row.mfa_secret = None
                    row.mfa_last_step = None
                logger.info("Refreshed demo staff user username=%s", username)
        session.commit()


def first_demo_credentials(settings: Settings) -> tuple[str, str] | None:
    specs = parse_demo_user_specs(settings.clerk_demo_users)
    if not specs:
        return None
    username, password, _ = specs[0]
    return username, password
