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
            return_value=(True, None),
        ),
    ):
        approved = client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    assert approved.status_code == 200

    outbox = client.get("/api/outbox", headers=owner_auth)
    latest = outbox.json()[0]
    assert latest["to_email"] == "james@example.com"
    assert latest["channel"] == "email"
    assert latest["delivered"] is True
    assert "not held until approved" not in latest["body"].lower()
    assert "now held" in latest["body"].lower()

    records = client.get("/api/records", headers=owner_auth)
    assert records.status_code == 200
    james = next(row for row in records.json() if row["email"] == "james@example.com")
    assert james["booking_state"] == "held"
    assert james["booking_day"] == "Thursday"
    assert james["booking_time"] == "10:00"


def test_reject_booking_marks_the_record_declined(
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
    assert msg.status_code == 200, msg.text
    assert msg.json()["record"]["booking_state"] == "prepared"
    task_id = msg.json()["task_id"]
    rejected = client.post(f"/api/queue/{task_id}/reject", headers=owner_auth)
    assert rejected.status_code == 200
    records = client.get("/api/records", headers=owner_auth)
    james = next(row for row in records.json() if row["email"] == "james@example.com")
    assert james["booking_state"] == "declined"
    assert "nothing was sent" in james["note"].lower()


def test_invalid_phone_is_rejected(client: TestClient, owner_auth: dict[str, str]) -> None:
    created = client.post(
        "/api/inbox",
        headers=owner_auth,
        json={
            "from_name": "Thandi Jacobs",
            "from_email": "thandi@example.com",
            "subject": "Fee",
            "body": "Please WhatsApp me the standard session fee.",
            "channel": "WhatsApp",
            "phone": "nope",
        },
    )
    assert created.status_code == 422


def test_whatsapp_approval_does_not_email(
    client: TestClient,
    owner_auth: dict[str, str],
) -> None:
    created = client.post(
        "/api/inbox",
        headers=owner_auth,
        json={
            "from_name": "Thandi Jacobs",
            "from_email": "thandi@example.com",
            "subject": "Fee",
            "body": "Please WhatsApp me the standard session fee.",
            "channel": "WhatsApp",
            "phone": "+27820000000",
        },
    )
    assert created.status_code == 200, created.text
    inbound_id = created.json()["id"]
    msg = client.post(
        "/api/messages",
        headers=owner_auth,
        json={
            "text": "Please WhatsApp me the standard session fee.",
            "sample_id": "whatsapp_session_fee",
            "inbound_id": inbound_id,
        },
    )
    assert msg.status_code == 200, msg.text
    body = msg.json()
    assert body["queue_status"] == "pending"
    assert body["record"]["last_channel"] == "WhatsApp"
    assert body["record"]["phone"] == "+27820000000"
    assert body["record"]["booking_state"] == "none"
    assert "waiting for approval" in body["record"]["note"].lower()
    task_id = body["task_id"]

    with (
        patch("clerk.services.outbound_delivery.smtp_configured", return_value=True),
        patch(
            "clerk.services.outbound_delivery.send_plain_email",
            new_callable=AsyncMock,
        ) as send_email,
    ):
        approved = client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    assert approved.status_code == 200
    send_email.assert_not_called()

    outbox = client.get("/api/outbox", headers=owner_auth)
    latest = outbox.json()[0]
    assert latest["channel"] == "whatsapp"
    assert latest["to_phone"] == "+27820000000"
    assert latest["delivered"] is False
    assert "not sent" in (latest["delivery_error"] or "").lower() or "nothing was sent" in (
        latest["delivery_error"] or ""
    ).lower()

    records = client.get("/api/records", headers=owner_auth)
    thandi = next(row for row in records.json() if row["email"] == "thandi@example.com")
    assert "not sent to a phone" in thandi["note"].lower()
