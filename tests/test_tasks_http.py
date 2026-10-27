import os

import pytest
from fastapi.testclient import TestClient

from clerk.main import create_app


@pytest.fixture
def client(tmp_path) -> TestClient:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'http.db'}"
    os.environ["CLERK_BOOTSTRAP_STAFF"] = "owner:test-pass-99:manager"
    os.environ["SESSION_SECRET"] = "test-secret"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["PAGES_DIR"] = "pages"
    os.environ["OPENAI_API_KEY"] = ""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_login_and_demo_flow(client: TestClient) -> None:
    live = client.get("/api/live")
    assert live.status_code == 200

    blocked = client.post(
        "/api/messages",
        json={"text": "hello", "sample_id": "after_hours_thursday"},
    )
    assert blocked.status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "test-pass-99"},
    )
    assert login.status_code == 200

    sent = client.post(
        "/api/messages",
        json={"text": "Do you have anything on Thursday?", "sample_id": "after_hours_thursday"},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["outcome_kind"] == "sent_auto"

    outbox = client.get("/api/outbox")
    assert outbox.status_code == 200
    assert len(outbox.json()) >= 1

    booking = client.post(
        "/api/messages",
        json={"text": "Thursday 10:00", "sample_id": "booking_thursday_10"},
    )
    assert booking.status_code == 200
    assert booking.json()["outcome_kind"] == "queued"

    queue = client.get("/api/queue")
    assert queue.status_code == 200
    pending = queue.json()
    assert len(pending) >= 1
    task_id = pending[0]["id"]
    assert pending[0]["slot_held"] is False

    approved = client.post(f"/api/queue/{task_id}/approve")
    assert approved.status_code == 200

    queue_after = client.get("/api/queue")
    assert all(item["id"] != task_id for item in queue_after.json())
