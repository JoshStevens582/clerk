from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_staff_can_add_inbound_and_run_clerk(
    client: TestClient,
    owner_auth: dict[str, str],
) -> None:
    created = client.post(
        "/api/inbox",
        headers=owner_auth,
        json={
            "from_name": "Test Patient",
            "from_email": "patient@example.com",
            "subject": "Thursday?",
            "body": "Do you have anything on Thursday?",
        },
    )
    assert created.status_code == 200
    inbound_id = created.json()["id"]

    handled = client.post(
        "/api/messages",
        headers=owner_auth,
        json={
            "text": "Do you have anything on Thursday?",
            "sample_id": "after_hours_thursday",
            "inbound_id": inbound_id,
        },
    )
    assert handled.status_code == 200

    inbox = client.get("/api/inbox", headers=owner_auth)
    assert all(item["id"] != inbound_id for item in inbox.json())


def test_inbound_webhook_requires_secret(client: TestClient) -> None:
    denied = client.post(
        "/api/hooks/inbound",
        json={
            "from_name": "Webhook",
            "from_email": "hook@example.com",
            "subject": "Hi",
            "body": "Hello",
        },
    )
    assert denied.status_code in {401, 503}


def test_approve_delivers_when_smtp_mocked(
    client: TestClient,
    owner_auth: dict[str, str],
) -> None:
    created = client.post(
        "/api/inbox",
        headers=owner_auth,
        json={
            "from_name": "James Patel",
            "from_email": "james@example.com",
            "subject": "Book Thursday",
            "body": "Please book me for Thursday at 10:00.",
        },
    )
    inbound_id = created.json()["id"]
    msg = client.post(
        "/api/messages",
        headers=owner_auth,
        json={
            "text": "Please book me for Thursday at 10:00.",
            "sample_id": "booking_thursday_10",
            "inbound_id": inbound_id,
        },
    )
    task_id = msg.json()["task_id"]

    with (
        patch("clerk.services.outbound_delivery.smtp_configured", return_value=True),
        patch(
            "clerk.services.outbound_delivery.send_plain_email",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        approved = client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    assert approved.status_code == 200

    outbox = client.get("/api/outbox", headers=owner_auth)
    latest = outbox.json()[0]
    assert latest["to_email"] == "james@example.com"
    assert latest["delivered"] is True
