"""Create staff users on the server (managers run this after SSH)."""

import argparse
import getpass
import sys

from clerk.config import load_settings
from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.repositories.staff_repo import StaffRepository
from clerk.schemas.staff import StaffRole
from clerk.services.staff_auth import hash_password


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Add a Clerk staff user.")
    parser.add_argument("username", help="Login name (lowercase letters, digits, _ -)")
    parser.add_argument("--role", choices=("staff", "manager"), default="staff")
    parser.add_argument("--display-name", default=None)
    parser.add_argument(
        "--password",
        default=None,
        help="Set on the server only; omit locally to be prompted.",
    )
    args = parser.parse_args(argv)

    if args.password is not None:
        password = args.password
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm: ")
        if password != confirm:
            print("Passwords did not match.", file=sys.stderr)
            raise SystemExit(1)
    if len(password) < 8:
        print("Use at least 8 characters.", file=sys.stderr)
        raise SystemExit(1)

    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    factory = session_factory(engine)
    role: StaffRole = "manager" if args.role == "manager" else "staff"

    username = args.username.strip().lower()
    with factory() as session:
        repo = StaffRepository(session)
        existing = repo.get_by_username(username)
        if existing is not None:
            existing.password_hash = hash_password(password)
            existing.active = True
            if args.role == "manager" or existing.role == "manager":
                existing.role = role if args.role == "manager" else existing.role
            session.commit()
            print(f"Updated password for staff user {username} ({existing.role}).")
            return
        repo.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            display_name=args.display_name,
        )
        session.commit()
    print(f"Created staff user {username} ({role}).")


if __name__ == "__main__":
    main()
