"""Staff accounts for the Clerk desk (v2)."""

import logging
import re

import bcrypt
from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import StaffRole, StaffUserOut

logger = logging.getLogger("clerk.staff")

_USERNAME_RE = re.compile(r"^[a-z0-9_-]+$")
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def staff_user_out(row: object) -> StaffUserOut:
    from clerk.repositories.models import StaffUserRow

    if not isinstance(row, StaffUserRow):
        raise TypeError("Expected StaffUserRow")
    role: StaffRole = "manager" if row.role == "manager" else "staff"
    return StaffUserOut(
        username=row.username,
        role=role,
        display_name=row.display_name,
        email=row.email,
    )


def authenticate(
    session: Session,
    *,
    username: str,
    password: str,
) -> StaffUserOut | None:
    repo = StaffRepository(session)
    row = repo.get_by_username(username)
    if row is None or not row.active:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, row.password_hash):
        return None
    return staff_user_out(row)


def parse_bootstrap_spec(raw: str) -> list[tuple[str, str, StaffRole]]:
    """Parse ``user:pass`` or ``user:pass:role`` entries separated by commas."""
    entries: list[tuple[str, str, StaffRole]] = []
    for chunk in raw.split(","):
        piece = chunk.strip()
        if not piece:
            continue
        parts = piece.split(":")
        if len(parts) < 2:
            raise ValueError(f"Invalid staff bootstrap entry: {piece!r}")
        username = parts[0].strip().lower()
        password = parts[1]
        role: StaffRole = "staff"
        if len(parts) >= 3 and parts[2].strip():
            role = "manager" if parts[2].strip() == "manager" else "staff"
        if not _USERNAME_RE.match(username):
            raise ValueError(f"Invalid username in bootstrap: {username!r}")
        entries.append((username, password, role))
    return entries


def bootstrap_staff_users(settings: Settings, db_factory: sessionmaker[Session]) -> None:
    with db_factory() as session:
        repo = StaffRepository(session)
        if repo.count_users() > 0:
            return

        specs: list[tuple[str, str, StaffRole]] = []
        if settings.clerk_bootstrap_staff.strip():
            specs.extend(parse_bootstrap_spec(settings.clerk_bootstrap_staff))
        elif settings.owner_password.strip():
            specs.append(("owner", settings.owner_password, "manager"))

        if not specs:
            specs = [
                ("owner", "demo-owner", "manager"),
                ("reception", "demo-reception", "staff"),
            ]

        admin_names = {
            name.strip().lower()
            for name in settings.clerk_admin_usernames.split(",")
            if name.strip()
        }
        for username, password, role in specs:
            effective_role: StaffRole = "manager" if username in admin_names else role
            repo.create_user(
                username=username,
                password_hash=hash_password(password),
                role=effective_role,
                display_name=None,
            )
            logger.info("Seeded staff user username=%s role=%s", username, effective_role)
        session.commit()
