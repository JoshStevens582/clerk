from fastapi.testclient import TestClient


def test_login_and_demo_flow(client: TestClient, owner_auth: dict[str, str]) -> None:
    live = client.get("/api/live")
    assert live.status_code == 200

    blocked = client.post(
        "/api/messages",
        json={"text": "hello", "sample_id": "after_hours_thursday"},
    )
    assert blocked.status_code == 401

    sent = client.post(
        "/api/messages",
        headers=owner_auth,
        json={"text": "Do you have anything on Thursday?", "sample_id": "after_hours_thursday"},
    )
    assert sent.status_code == 200

    queue = client.get("/api/queue", headers=owner_auth)
    assert queue.status_code == 200

    login = client.post("/api/auth/login", json={"username": "owner", "password": "test-pass-99"})
    refresh_token = login.json().get("refresh_token")
    assert refresh_token
    refresh = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 200
    assert refresh.json().get("access_token")
