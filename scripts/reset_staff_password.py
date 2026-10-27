"""One-off password reset inside the clerk-api container."""

import sys

from clerk.config import load_settings
from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.repositories.staff_repo import StaffRepository
from clerk.services.staff_auth import hash_password


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: reset_staff_password.py USERNAME PASSWORD", file=sys.stderr)
        raise SystemExit(2)
    username = sys.argv[1].strip().lower()
    password = sys.argv[2]
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        raise SystemExit(1)
    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    factory = session_factory(engine)
    with factory() as session:
        row = StaffRepository(session).get_by_username(username)
        if row is None:
            print(f"No staff user named {username!r}.", file=sys.stderr)
            raise SystemExit(1)
        row.password_hash = hash_password(password)
        row.active = True
        session.commit()
    print(f"Password updated for {username}.")


if __name__ == "__main__":
    main()
