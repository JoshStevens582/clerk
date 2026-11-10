import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from clerk.repositories.inbound_repo import InboundRepository
from clerk.services.outbound_delivery import deliver_outbox_for_task
from conftest import WHATSAPP_TEST_APP_SECRET, WHATSAPP_TEST_VERIFY_TOKEN


def _queue_whatsapp_draft(client: TestClient, auth: dict[str, str]) -> int:
    created = client.post(
        "/api/inbox",
        headers=auth,
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
    handled = client.post(
        "/api/messages",
        headers=auth,
        json={
            "text": "Please WhatsApp me the standard session fee.",
            "sample_id": "whatsapp_session_fee",
            "inbound_id": created.json()["id"],
        },
    )
    assert handled.status_code == 200, handled.text
    assert handled.json()["queue_status"] == "pending"
    return int(handled.json()["task_id"])


def test_approved_whatsapp_is_sent_to_the_phone(
    client: TestClient, owner_auth: dict[str, str]
) -> None:
    task_id = _queue_whatsapp_draft(client, owner_auth)
    with (
        patch("clerk.services.outbound_delivery.whatsapp_send_configured", return_value=True),
        patch(
            "clerk.services.outbound_delivery.send_whatsapp_text",
            new_callable=AsyncMock,
            return_value=(True, None),
        ) as send,
        patch("clerk.services.outbound_delivery.send_plain_email", new_callable=AsyncMock) as mail,
    ):
        approved = client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    assert approved.status_code == 200
    mail.assert_not_called()
    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.kwargs["to_phone"] == "+27820000000"
    assert "R650" in send.await_args.kwargs["body"]

    latest = client.get("/api/outbox", headers=owner_auth).json()[0]
    assert latest["channel"] == "whatsapp"
    assert latest["delivered"] is True
    assert latest["delivery_error"] is None


def test_failed_whatsapp_send_stays_undelivered_with_the_reason(
    client: TestClient, owner_auth: dict[str, str]
) -> None:
    task_id = _queue_whatsapp_draft(client, owner_auth)
    with (
        patch("clerk.services.outbound_delivery.whatsapp_send_configured", return_value=True),
        patch(
            "clerk.services.outbound_delivery.send_whatsapp_text",
            new_callable=AsyncMock,
            return_value=(False, "WhatsApp refused it: more than 24 hours."),
        ),
    ):
        client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    latest = client.get("/api/outbox", headers=owner_auth).json()[0]
    assert latest["delivered"] is False
    assert latest["delivery_error"] == "WhatsApp refused it: more than 24 hours."


async def test_demo_desk_never_sends_whatsapp(
    client: TestClient, owner_auth: dict[str, str]
) -> None:
    task_id = _queue_whatsapp_draft(client, owner_auth)
    client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    app = client.app
    with patch(
        "clerk.services.outbound_delivery.send_whatsapp_text", new_callable=AsyncMock
    ) as send:
        delivered = await deliver_outbox_for_task(
            app.state.settings,  # type: ignore[attr-defined]
            app.state.db_factory,  # type: ignore[attr-defined]
            task_id=task_id,
            demo_dry_run=True,
        )
    assert delivered is True
    send.assert_not_called()
    latest = client.get("/api/outbox", headers=owner_auth).json()[0]
    assert latest["delivery_error"] == "Demo desk. Not sent on WhatsApp."


def test_whatsapp_without_a_phone_is_not_sent(
    client: TestClient, owner_auth: dict[str, str]
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
        },
    )
    handled = client.post(
        "/api/messages",
        headers=owner_auth,
        json={
            "text": "Please WhatsApp me the standard session fee.",
            "sample_id": "whatsapp_session_fee",
            "inbound_id": created.json()["id"],
        },
    )
    task_id = handled.json()["task_id"]
    with (
        patch("clerk.services.outbound_delivery.whatsapp_send_configured", return_value=True),
        patch(
            "clerk.services.outbound_delivery.send_whatsapp_text", new_callable=AsyncMock
        ) as send,
    ):
        client.post(f"/api/queue/{task_id}/approve", headers=owner_auth)
    send.assert_not_called()
    latest = client.get("/api/outbox", headers=owner_auth).json()[0]
    assert latest["delivered"] is False
    assert latest["delivery_error"] == "No phone number on this message."


def test_agreed_reply_on_whatsapp_goes_out_on_whatsapp(
    client: TestClient, owner_auth: dict[str, str]
) -> None:
    created = client.post(
        "/api/inbox",
        headers=owner_auth,
        json={
            "from_name": "Thandi Jacobs",
            "from_email": "thandi@example.com",
            "subject": "Thursday",
            "body": "Do you have anything on Thursday?",
            "channel": "WhatsApp",
            "phone": "+27820000000",
        },
    )
    with (
        patch("clerk.services.outbound_delivery.whatsapp_send_configured", return_value=True),
        patch(
            "clerk.services.outbound_delivery.send_whatsapp_text",
            new_callable=AsyncMock,
            return_value=(True, None),
        ) as send,
    ):
        handled = client.post(
            "/api/messages",
            headers=owner_auth,
            json={
                "text": "Do you have anything on Thursday?",
                "sample_id": "after_hours_thursday",
                "inbound_id": created.json()["id"],
            },
        )
    assert handled.status_code == 200, handled.text
    assert handled.json()["outcome_kind"] == "sent_auto"
    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.kwargs["body"] == handled.json()["auto_reply_text"]


def test_webhook_verification(client: TestClient) -> None:
    ok = client.get(
        "/api/hooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": WHATSAPP_TEST_VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    assert ok.status_code == 200
    assert ok.text == "12345"
    wrong = client.get(
        "/api/hooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"},
    )
    assert wrong.status_code == 403
    client.app.state.settings.whatsapp_verify_token = ""  # type: ignore[attr-defined]
    off = client.get("/api/hooks/whatsapp", params={"hub.mode": "subscribe"})
    assert off.status_code == 503


def _signed(body: bytes) -> dict[str, str]:
    digest = hmac.new(WHATSAPP_TEST_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


def _text_event(message_id: str) -> bytes:
    event: dict[str, Any] = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "27820000000", "profile": {"name": "Thandi"}}],
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "27820000000",
                                    "type": "text",
                                    "text": {"body": "What is the session fee?"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }
    return json.dumps(event).encode()


def test_webhook_rejects_a_bad_signature(client: TestClient) -> None:
    body = _text_event("wamid.bad")
    response = client.post(
        "/api/hooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=0000", "Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_webhook_rejects_bad_json(client: TestClient) -> None:
    body = b"not json"
    response = client.post("/api/hooks/whatsapp", content=body, headers=_signed(body))
    assert response.status_code == 400


def test_webhook_off_without_app_secret(client: TestClient) -> None:
    client.app.state.settings.whatsapp_app_secret = ""  # type: ignore[attr-defined]
    body = _text_event("wamid.off")
    response = client.post("/api/hooks/whatsapp", content=body, headers=_signed(body))
    assert response.status_code == 503


def test_webhook_stores_the_message_once_and_runs_clerk(client: TestClient) -> None:
    body = _text_event("wamid.in-1")
    first = client.post("/api/hooks/whatsapp", content=body, headers=_signed(body))
    second = client.post("/api/hooks/whatsapp", content=body, headers=_signed(body))
    assert first.status_code == 200
    assert second.status_code == 200

    db_factory = client.app.state.db_factory  # type: ignore[attr-defined]
    with db_factory() as session:
        row = InboundRepository(session).get_by_external_id("wa:wamid.in-1")
        assert row is not None
        assert row.channel == "WhatsApp"
        assert row.phone == "+27820000000"
        assert row.from_name == "Thandi"
        assert row.body == "What is the session fee?"
        assert row.task_id is None
        assert row.clerk_note is not None
        assert row.clerk_note.startswith("Clerk could not answer from your pages:")
        same = [
            r
            for r in InboundRepository(session).list_recent(limit=500)
            if r.external_id == "wa:wamid.in-1"
        ]
        assert len(same) == 1
