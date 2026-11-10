from unittest.mock import patch

from fastapi.testclient import TestClient

from clerk.schemas.agent import PolicyOutcomeKind
from clerk.services.workflow import unanswered_note


def _add_inbound(client: TestClient, auth: dict[str, str], body: str) -> int:
    created = client.post(
        "/api/inbox",
        headers=auth,
        json={
            "from_name": "Thandi Jacobs",
            "from_email": "thandi@example.com",
            "subject": "Question",
            "body": body,
            "channel": "WhatsApp",
            "phone": "+27820000000",
        },
    )
    assert created.status_code == 200, created.text
    return int(created.json()["id"])


def _run_clerk(
    client: TestClient, auth: dict[str, str], inbound_id: int, body: str, sample_id: str | None
) -> dict[str, object]:
    handled = client.post(
        "/api/messages",
        headers=auth,
        json={"text": body, "inbound_id": inbound_id, "sample_id": sample_id},
    )
    assert handled.status_code == 200, handled.text
    result: dict[str, object] = handled.json()
    return result


def _inbox_row(client: TestClient, auth: dict[str, str], inbound_id: int) -> dict[str, object]:
    rows = client.get("/api/inbox", headers=auth).json()
    matches = [row for row in rows if row["id"] == inbound_id]
    assert len(matches) == 1
    row: dict[str, object] = matches[0]
    return row


def test_unanswered_message_stays_in_the_inbox_with_a_note(
    client: TestClient, owner_auth: dict[str, str]
) -> None:
    body = "What services do you offer?"
    inbound_id = _add_inbound(client, owner_auth, body)
    result = _run_clerk(client, owner_auth, inbound_id, body, None)
    assert result["outcome_kind"] == "needs_info"

    row = _inbox_row(client, owner_auth, inbound_id)
    assert row["handled"] is False
    assert isinstance(row["clerk_note"], str)
    assert row["clerk_note"].startswith("Clerk could not answer from your pages:")


def test_mark_done_takes_it_off_the_list(client: TestClient, owner_auth: dict[str, str]) -> None:
    body = "What services do you offer?"
    inbound_id = _add_inbound(client, owner_auth, body)
    _run_clerk(client, owner_auth, inbound_id, body, None)

    done = client.post(f"/api/inbox/{inbound_id}/done", headers=owner_auth)
    assert done.status_code == 200, done.text
    open_ids = [row["id"] for row in client.get("/api/inbox", headers=owner_auth).json()]
    assert inbound_id not in open_ids

    again = client.post(f"/api/inbox/{inbound_id}/done", headers=owner_auth)
    assert again.status_code == 200


def test_mark_done_needs_clerk_to_have_looked_first(
    client: TestClient, owner_auth: dict[str, str]
) -> None:
    inbound_id = _add_inbound(client, owner_auth, "Hello")
    early = client.post(f"/api/inbox/{inbound_id}/done", headers=owner_auth)
    assert early.status_code == 409

    missing = client.post("/api/inbox/999999/done", headers=owner_auth)
    assert missing.status_code == 404


def test_demo_desk_cannot_mark_done(client: TestClient, owner_auth: dict[str, str]) -> None:
    inbound_id = _add_inbound(client, owner_auth, "Hello")
    with patch("clerk.api.routers.inbox.is_demo_staff", return_value=True):
        response = client.post(f"/api/inbox/{inbound_id}/done", headers=owner_auth)
    assert response.status_code == 403


def test_a_later_draft_clears_the_note(client: TestClient, owner_auth: dict[str, str]) -> None:
    body = "Please WhatsApp me the standard session fee."
    inbound_id = _add_inbound(client, owner_auth, body)
    _run_clerk(client, owner_auth, inbound_id, body, None)
    assert _inbox_row(client, owner_auth, inbound_id)["clerk_note"] is not None

    result = _run_clerk(client, owner_auth, inbound_id, body, "whatsapp_session_fee")
    assert result["queue_status"] == "pending"
    open_ids = [row["id"] for row in client.get("/api/inbox", headers=owner_auth).json()]
    assert inbound_id not in open_ids


def test_note_wording() -> None:
    assert unanswered_note(PolicyOutcomeKind.NEEDS_INFO, "No services page.") == (
        "Clerk could not answer from your pages: No services page."
    )
    assert unanswered_note(PolicyOutcomeKind.BLOCKED, "Draft must cite at least one page.") == (
        "Clerk stopped its draft: Draft must cite at least one page."
    )
