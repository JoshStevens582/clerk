import os

import pytest
from fastapi.testclient import TestClient

from clerk.main import create_app
from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService

TEST_AUTH_SECRET = "test-clerk-auth-secret-at-least-32-bytes"


@pytest.fixture
def policy() -> PolicyService:
    return PolicyService(PageStore("pages"))


@pytest.fixture
def client(tmp_path) -> TestClient:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'clerk.db'}"
    os.environ["CLERK_BOOTSTRAP_STAFF"] = "owner:test-pass-99:manager,reception:test-pass-99:staff"
    os.environ["CLERK_AUTH_SECRET"] = TEST_AUTH_SECRET
    os.environ["LOGIN_LOCKOUT_ENABLED"] = "false"
    os.environ["RATE_LIMIT_FAIL_CLOSED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["PAGES_DIR"] = "pages"
    os.environ["OPENAI_API_KEY"] = ""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _login_headers(client: TestClient, *, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("access_token"), body
    token = body["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_auth(client: TestClient) -> dict[str, str]:
    return _login_headers(client, username="owner", password="test-pass-99")


@pytest.fixture
def reception_auth(client: TestClient) -> dict[str, str]:
    return _login_headers(client, username="reception", password="test-pass-99")
