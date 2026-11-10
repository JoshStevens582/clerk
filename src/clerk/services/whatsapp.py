"""WhatsApp Cloud API: send an approved text, verify and read inbound webhooks."""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from clerk.config import Settings

logger = logging.getLogger("clerk.whatsapp")

GRAPH_API_BASE = "https://graph.facebook.com"
# Meta error code when a free-form reply is outside the 24-hour customer window.
_OUTSIDE_WINDOW_CODE = 131047
_MAX_TEXT_LENGTH = 4096


@dataclass(frozen=True)
class InboundWhatsAppText:
    message_id: str
    phone: str
    name: str
    text: str


def whatsapp_send_configured(settings: Settings) -> bool:
    return bool(settings.whatsapp_access_token.strip()) and bool(
        settings.whatsapp_phone_number_id.strip()
    )


def whatsapp_recipient(phone: str, *, default_country_code: str) -> str | None:
    """Digits only, with country code, as the Cloud API expects. None if unusable."""
    digits = "".join(char for char in phone if char.isdigit())
    if phone.strip().startswith("+"):
        recipient = digits
    elif digits.startswith("00"):
        recipient = digits[2:]
    elif digits.startswith("0"):
        country = "".join(char for char in default_country_code if char.isdigit())
        if not country:
            return None
        recipient = country + digits[1:]
    else:
        recipient = digits
    if not 8 <= len(recipient) <= 15:
        return None
    return recipient


def _error_detail(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        return f"WhatsApp send failed ({response.status_code})."
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return f"WhatsApp send failed ({response.status_code})."
    if error.get("code") == _OUTSIDE_WINDOW_CODE:
        return (
            "WhatsApp refused it: more than 24 hours since the customer's last message. "
            "Reply from WhatsApp directly, or wait for them to message again."
        )
    message = str(error.get("message") or "").strip()
    if message:
        return f"WhatsApp send failed: {message}"[:500]
    return f"WhatsApp send failed ({response.status_code})."


async def send_whatsapp_text(
    settings: Settings,
    *,
    to_phone: str,
    body: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, str | None]:
    if not whatsapp_send_configured(settings):
        return False, "WhatsApp is not connected."
    recipient = whatsapp_recipient(
        to_phone, default_country_code=settings.whatsapp_default_country_code
    )
    if recipient is None:
        return False, "The phone number cannot be used on WhatsApp."
    text = body.strip()
    if not text:
        return False, "The WhatsApp message is empty."
    if len(text) > _MAX_TEXT_LENGTH:
        return False, f"The WhatsApp message is over {_MAX_TEXT_LENGTH} characters."

    version = settings.whatsapp_api_version.strip() or "v23.0"
    phone_number_id = settings.whatsapp_phone_number_id.strip()
    url = f"{GRAPH_API_BASE}/{version}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token.strip()}"}
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=30.0) as owned_client:
                response = await owned_client.post(url, json=payload, headers=headers)
        else:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp send failed (network): %s", type(exc).__name__)
        return False, "WhatsApp could not be reached. Try approving again later."
    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("WhatsApp send rejected status=%s", response.status_code)
        return False, detail
    return True, None


def verify_meta_signature(*, body: bytes, app_secret: str, signature_header: str) -> bool:
    """Check X-Hub-Signature-256 (sha256=<hex>) against the raw request body."""
    secret = app_secret.strip()
    provided = signature_header.strip()
    if not secret or not provided.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided.removeprefix("sha256="), expected)


def parse_inbound_texts(payload: Any) -> tuple[list[InboundWhatsAppText], int]:
    """Text messages from a Cloud API webhook, plus a count of skipped non-text messages."""
    found: list[InboundWhatsAppText] = []
    skipped = 0
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return found, skipped
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            value = change.get("value") if isinstance(change, dict) else None
            if not isinstance(value, dict):
                continue
            names: dict[str, str] = {}
            for contact in value.get("contacts") or []:
                if not isinstance(contact, dict):
                    continue
                wa_id = str(contact.get("wa_id") or "")
                profile = contact.get("profile")
                name = profile.get("name") if isinstance(profile, dict) else None
                if wa_id and isinstance(name, str) and name.strip():
                    names[wa_id] = name.strip()
            for message in value.get("messages") or []:
                if not isinstance(message, dict):
                    continue
                message_id = str(message.get("id") or "").strip()
                sender = str(message.get("from") or "").strip()
                text_block = message.get("text")
                text = text_block.get("body") if isinstance(text_block, dict) else None
                if message.get("type") != "text" or not isinstance(text, str) or not text.strip():
                    skipped += 1
                    continue
                if not message_id or not sender.isdigit():
                    skipped += 1
                    continue
                found.append(
                    InboundWhatsAppText(
                        message_id=message_id,
                        phone=f"+{sender}",
                        name=names.get(sender, ""),
                        text=text.strip(),
                    )
                )
    return found, skipped
