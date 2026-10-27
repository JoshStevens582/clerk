import os

import pytest
from fastapi.testclient import TestClient

from clerk.main import create_app

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
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_demo_status_available(demo_client: TestClient) -> None:
    response = demo_client.get("/api/auth/demo-status")
    assert response.status_code == 200
    assert response.json()["available"] is True


def test_demo_login_returns_tokens(demo_client: TestClient) -> None:
    response = demo_client.post("/api/auth/demo")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == "demo"
    assert body["access_token"]
    assert body["refresh_token"]


def test_demo_inbox_only_sample_rows(demo_client: TestClient) -> None:
    owner = demo_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "test-pass-99"},
    )
    assert owner.status_code == 200
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}

    demo_client.post(
        "/api/inbox",
        json={
            "from_name": "Real Patient",
            "from_email": "real@patient.co.za",
            "subject": "Live mail",
            "body": "Should not appear for demo.",
            "channel": "Email",
        },
        headers=owner_headers,
    )

    demo = demo_client.post("/api/auth/demo")
    assert demo.status_code == 200
    demo_headers = {"Authorization": f"Bearer {demo.json()['access_token']}"}

    inbox = demo_client.get("/api/inbox", headers=demo_headers)
    assert inbox.status_code == 200
    rows = inbox.json()
    assert all(row.get("sample_id") for row in rows)
    assert not any(row["from_email"] == "real@patient.co.za" for row in rows)
