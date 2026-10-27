from clerk.config import Settings
from clerk.services.resend_inbound import (
    ResendApiAccess,
    inbound_automation_ready,
    probe_resend_api_access_sync,
)


def test_inbound_automation_requires_full_access() -> None:
    settings = Settings(
        resend_api_key="re_test",
        clerk_inbound_address="clerk@example.com",
    )
    assert not inbound_automation_ready(settings, resend_api_access=ResendApiAccess.SEND_ONLY)
    assert inbound_automation_ready(settings, resend_api_access=ResendApiAccess.FULL)


def test_probe_send_only(monkeypatch) -> None:
    class FakeResponse:
        status_code = 401

        def json(self) -> dict[str, str]:
            return {"name": "restricted_api_key"}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs):
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)
    settings = Settings(resend_api_key="re_x", smtp_host="smtp.resend.com", smtp_password="")
    assert probe_resend_api_access_sync(settings) == ResendApiAccess.SEND_ONLY
