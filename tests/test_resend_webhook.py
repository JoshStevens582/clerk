import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_resend_webhook_queues_ingest(client: TestClient) -> None:
    payload = {
        "type": "email.received",
        "data": {"email_id": "email-abc-123"},
    }
    with patch(
        "clerk.api.routers.hooks.ingest_resend_received_email",
        new_callable=AsyncMock,
    ) as ingest:
        response = client.post(
            "/api/hooks/resend",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    ingest.assert_called_once()
