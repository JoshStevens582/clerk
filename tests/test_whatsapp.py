import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest

from clerk.config import Settings
from clerk.services.whatsapp import (
    parse_inbound_texts,
    send_whatsapp_text,
    verify_meta_signature,
    whatsapp_recipient,
    whatsapp_send_configured,
)


def _settings(**overrides: str) -> Settings:
    values = {
        "whatsapp_access_token": "token-x",
        "whatsapp_phone_number_id": "1234567890",
        "whatsapp_api_version": "v23.0",
        "whatsapp_default_country_code": "27",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+27 82 000 0000", "27820000000"),
        ("082 000 0000", "27820000000"),
        ("0027820000000", "27820000000"),
        ("27820000000", "27820000000"),
        ("+44 20 7946 0000", "442079460000"),
        ("123", None),
        ("", None),
    ],
)
def test_whatsapp_recipient(raw: str, expected: str | None) -> None:
    assert whatsapp_recipient(raw, default_country_code="27") == expected


def test_local_number_without_country_code_is_unusable() -> None:
    assert whatsapp_recipient("082 000 0000", default_country_code="") is None


def test_send_configured_needs_token_and_number_id() -> None:
    assert whatsapp_send_configured(_settings())
    assert not whatsapp_send_configured(_settings(whatsapp_access_token=""))
    assert not whatsapp_send_configured(_settings(whatsapp_phone_number_id=" "))


async def test_send_posts_text_to_graph_api() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["json"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    async with _client(handler) as client:
        sent, error = await send_whatsapp_text(
            _settings(), to_phone="+27 82 000 0000", body=" Fee is R650. ", client=client
        )
    assert (sent, error) == (True, None)
    assert seen["url"] == "https://graph.facebook.com/v23.0/1234567890/messages"
    assert seen["auth"] == "Bearer token-x"
    assert seen["json"]["to"] == "27820000000"
    assert seen["json"]["type"] == "text"
    assert seen["json"]["text"]["body"] == "Fee is R650."


async def test_send_explains_the_24_hour_window() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": 131047, "message": "Re-engagement"}})

    async with _client(handler) as client:
        sent, error = await send_whatsapp_text(
            _settings(), to_phone="+27820000000", body="Hi", client=client
        )
    assert not sent
    assert error is not None and "24 hours" in error


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            httpx.Response(401, json={"error": {"code": 190, "message": "Token expired"}}),
            "WhatsApp send failed: Token expired",
        ),
        (httpx.Response(500, text="oops"), "WhatsApp send failed (500)."),
        (httpx.Response(400, json={"error": "bad"}), "WhatsApp send failed (400)."),
        (httpx.Response(400, json={"error": {"code": 1}}), "WhatsApp send failed (400)."),
    ],
)
async def test_send_reports_api_errors(response: httpx.Response, expected: str) -> None:
    async with _client(lambda request: response) as client:
        sent, error = await send_whatsapp_text(
            _settings(), to_phone="+27820000000", body="Hi", client=client
        )
    assert (sent, error) == (False, expected)


async def test_send_reports_network_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    async with _client(handler) as client:
        sent, error = await send_whatsapp_text(
            _settings(), to_phone="+27820000000", body="Hi", client=client
        )
    assert not sent
    assert error is not None and "could not be reached" in error


async def test_send_without_a_client_opens_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    def fake_client(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("clerk.services.whatsapp.httpx.AsyncClient", fake_client)
    assert await send_whatsapp_text(_settings(), to_phone="+27820000000", body="Hi") == (
        True,
        None,
    )


@pytest.mark.parametrize(
    ("settings", "phone", "body", "expected"),
    [
        (_settings(whatsapp_access_token=""), "+27820000000", "Hi", "not connected"),
        (_settings(), "12", "Hi", "cannot be used"),
        (_settings(), "+27820000000", "   ", "empty"),
        (_settings(), "+27820000000", "x" * 4097, "over 4096"),
    ],
)
async def test_send_refuses_before_calling_api(
    settings: Settings, phone: str, body: str, expected: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the API must not be called")

    async with _client(handler) as client:
        sent, error = await send_whatsapp_text(settings, to_phone=phone, body=body, client=client)
    assert not sent
    assert error is not None and expected in error


def test_verify_meta_signature() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    good = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body=body, app_secret="app-secret", signature_header=good)
    assert not verify_meta_signature(
        body=body + b" ", app_secret="app-secret", signature_header=good
    )
    assert not verify_meta_signature(body=body, app_secret="", signature_header=good)
    assert not verify_meta_signature(body=body, app_secret="app-secret", signature_header="abc")


def _event(messages: list[dict[str, Any]], contacts: list[Any] | None = None) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": contacts
                            if contacts is not None
                            else [{"wa_id": "27820000000", "profile": {"name": "Thandi"}}],
                            "messages": messages,
                        }
                    }
                ]
            }
        ],
    }


def test_parse_inbound_texts_reads_text_and_skips_the_rest() -> None:
    event = _event(
        [
            {"id": "wamid.1", "from": "27820000000", "type": "text", "text": {"body": " Fee? "}},
            {"id": "wamid.2", "from": "27820000000", "type": "image", "image": {}},
            {"id": "", "from": "27820000000", "type": "text", "text": {"body": "no id"}},
            {"id": "wamid.3", "from": "abc", "type": "text", "text": {"body": "bad sender"}},
            {"id": "wamid.4", "from": "27831111111", "type": "text", "text": {"body": "Hi"}},
            "not a dict",
        ],
        contacts=[
            {"wa_id": "27820000000", "profile": {"name": "Thandi"}},
            {"wa_id": "27831111111", "profile": "broken"},
            "not a dict",
        ],
    )
    messages, skipped = parse_inbound_texts(event)
    assert [(m.message_id, m.phone, m.name, m.text) for m in messages] == [
        ("wamid.1", "+27820000000", "Thandi", "Fee?"),
        ("wamid.4", "+27831111111", "", "Hi"),
    ]
    assert skipped == 3


@pytest.mark.parametrize(
    "event",
    [
        None,
        {"object": "page"},
        {"object": "whatsapp_business_account", "entry": ["x", {"changes": ["x", {}]}]},
    ],
)
def test_parse_inbound_texts_ignores_other_payloads(event: Any) -> None:
    assert parse_inbound_texts(event) == ([], 0)
