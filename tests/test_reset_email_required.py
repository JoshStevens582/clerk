import os

import pytest
from fastapi.testclient import TestClient

from clerk import staff_cli
from clerk.main import create_app
from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.repositories.staff_repo import StaffRepository

TEST_AUTH_SECRET = "test-clerk-auth-secret-at-least-32-bytes"


@pytest.fixture
def demo_client(tmp_path) -> TestClient:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'demo-clerk.db'}"
    os.environ["CLERK_BOOTSTRAP_STAFF"] = "owner:test-pass-99:manager"
    os.environ["CLERK_DEMO_USERS"] = "demo:demo-pass-88:staff"
    os.environ["CLERK_AUTH_SECRET"] = TEST_AUTH_SECRET
    os.environ["LOGIN_LOCKOUT_ENABLED"] = "false"
    os.environ["RATE_LIMIT_FAIL_CLOSED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["CLERK_SEED_DEMO_INBOX"] = "false"
    with TestClient(create_app()) as test_client:
        yield test_client


def _new_staff(email: str | None) -> dict[str, str]:
    body = {"username": "physio2", "password": "another-pass-99", "role": "staff"}
    if email is not None:
        body["email"] = email
    return body


def test_create_staff_requires_email(client: TestClient, owner_auth: dict[str, str]) -> None:
    missing = client.post("/api/staff/users", headers=owner_auth, json=_new_staff(None))
    assert missing.status_code == 422

    invalid = client.post("/api/staff/users", headers=owner_auth, json=_new_staff("not-an-email"))
    assert invalid.status_code == 422


def test_create_staff_rejects_email_in_use(
    client: TestClient,
    owner_auth: dict[str, str],
) -> None:
    saved = client.post(
        "/api/auth/profile/email",
        headers=owner_auth,
        json={"email": "owner@example.com"},
    )
    assert saved.status_code == 200

    taken = client.post(
        "/api/staff/users",
        headers=owner_auth,
        json=_new_staff("Owner@Example.com"),
    )
    assert taken.status_code == 409


def test_demo_account_cannot_set_reset_email(demo_client: TestClient) -> None:
    demo = demo_client.post("/api/auth/demo")
    assert demo.status_code == 200
    headers = {"Authorization": f"Bearer {demo.json()['access_token']}"}

    denied = demo_client.post(
        "/api/auth/profile/email",
        headers=headers,
        json={"email": "visitor@example.com"},
    )
    assert denied.status_code == 403


@pytest.fixture
def cli_db(tmp_path) -> str:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'cli.db'}"
    return os.environ["DATABASE_URL"]


def _email_for(database_url: str, username: str) -> str | None:
    engine = create_db_engine(database_url)
    init_db(engine)
    with session_factory(engine)() as session:
        row = StaffRepository(session).get_by_username(username)
        assert row is not None
        return row.email


def test_cli_new_user_needs_email(cli_db: str) -> None:
    with pytest.raises(SystemExit):
        staff_cli.main(["newbie", "--password", "long-enough-1"])


def test_cli_rejects_invalid_email(cli_db: str) -> None:
    with pytest.raises(SystemExit):
        staff_cli.main(["newbie", "--password", "long-enough-1", "--email", "nope"])


def test_cli_creates_and_updates_email(cli_db: str, capsys: pytest.CaptureFixture[str]) -> None:
    staff_cli.main(["newbie", "--password", "long-enough-1", "--email", "New@Example.com"])
    assert _email_for(cli_db, "newbie") == "new@example.com"

    staff_cli.main(["newbie", "--password", "long-enough-2"])
    assert _email_for(cli_db, "newbie") == "new@example.com"
    assert "no reset email" not in capsys.readouterr().err

    staff_cli.main(["newbie", "--password", "long-enough-3", "--email", "moved@example.com"])
    assert _email_for(cli_db, "newbie") == "moved@example.com"


def test_cli_rejects_email_owned_by_someone_else(cli_db: str) -> None:
    staff_cli.main(["first", "--password", "long-enough-1", "--email", "shared@example.com"])
    with pytest.raises(SystemExit):
        staff_cli.main(["second", "--password", "long-enough-1", "--email", "shared@example.com"])


def test_cli_warns_when_existing_user_has_no_email(
    cli_db: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine = create_db_engine(cli_db)
    init_db(engine)
    with session_factory(engine)() as session:
        StaffRepository(session).create_user(
            username="legacy",
            password_hash="x",
            role="staff",
            display_name=None,
        )
        session.commit()

    staff_cli.main(["legacy", "--password", "long-enough-1"])
    assert "no reset email" in capsys.readouterr().err
