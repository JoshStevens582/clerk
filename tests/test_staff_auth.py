import os

import pytest
from fastapi.testclient import TestClient

from clerk.main import create_app


@pytest.fixture
def client(tmp_path) -> TestClient:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'staff.db'}"
    os.environ["CLERK_BOOTSTRAP_STAFF"] = "owner:test-pass-99:manager,reception:test-pass-99:staff"
    os.environ["SESSION_SECRET"] = "test-secret"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["PAGES_DIR"] = "pages"
    os.environ["OPENAI_API_KEY"] = ""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_reception_can_use_the_desk(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"username": "reception", "password": "test-pass-99"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "staff"

    queue = client.get("/api/queue")
    assert queue.status_code == 200


def test_manager_can_list_staff_users(client: TestClient) -> None:
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "reception", "password": "test-pass-99"},
        ).status_code
        == 200
    )
    forbidden = client.get("/api/staff/users")
    assert forbidden.status_code == 403

    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "test-pass-99"},
        ).status_code
        == 200
    )
    users = client.get("/api/staff/users")
    assert users.status_code == 200
    names = {item["username"] for item in users.json()}
    assert names == {"owner", "reception"}


def test_manager_can_create_a_staff_user(client: TestClient) -> None:
    client.post("/api/auth/login", json={"username": "owner", "password": "test-pass-99"})
    created = client.post(
        "/api/staff/users",
        json={
            "username": "physio1",
            "password": "another-pass-99",
            "role": "staff",
        },
    )
    assert created.status_code == 201
    assert created.json()["username"] == "physio1"
