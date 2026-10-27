"""Resend receiving: webhook metadata + API fetch for body."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
from typing import Any

import httpx

from clerk.config import Settings
from clerk.services.email_address import split_from_address

logger = logging.getLogger("clerk.resend_inbound")

RESEND_API_BASE = "https://api.resend.com"


class ResendInboundError(Exception):
    pass


def effective_resend_api_key(settings: Settings) -> str:
    explicit = settings.resend_api_key.strip()
    if explicit:
        return explicit
    if settings.smtp_host.strip() == "smtp.resend.com":
        return settings.smtp_password.strip()
    return ""


def inbound_automation_ready(settings: Settings) -> bool:
    return bool(effective_resend_api_key(settings))


async def fetch_received_email_body(settings: Settings, *, email_id: str) -> tuple[str, str, str]:
    """Returns (from_raw, subject, plain_text_body)."""
    api_key = effective_resend_api_key(settings)
    if not api_key:
        raise ResendInboundError("RESEND_API_KEY is not configured.")
    url = f"{RESEND_API_BASE}/emails/receiving/{email_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    if response.status_code == 404:
        raise ResendInboundError("Received email not found at Resend.")
    if response.status_code >= 400:
        raise ResendInboundError(f"Resend API error ({response.status_code}).")
    payload: dict[str, Any] = response.json()
    from_raw = str(payload.get("from") or payload.get("headers", {}).get("from") or "")
    subject = str(payload.get("subject") or "(no subject)")
    text = str(payload.get("text") or "").strip()
    if not text:
        html = str(payload.get("html") or "").strip()
        text = html if html else subject
    if not text.strip():
        raise ResendInboundError("Received email had no text body.")
    return (from_raw, subject, text.strip())


def verify_svix_signature(
    *,
    body: bytes,
    secret: str,
    msg_id: str,
    timestamp: str,
    signature_header: str,
) -> bool:
    """Verify Resend/Svix webhook signature (whsec_ secret from dashboard)."""
    if not secret.strip():
        return False
    key_part = secret.strip()
    if key_part.startswith("whsec_"):
        key_part = key_part.removeprefix("whsec_")
    try:
        key = base64.b64decode(key_part)
    except (ValueError, binascii.Error):
        return False
    to_sign = f"{msg_id}.{timestamp}.{body.decode()}".encode()
    digest = hmac.new(key, to_sign, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    for piece in signature_header.split():
        if piece.startswith("v1,"):
            candidate = piece.removeprefix("v1,")
            if hmac.compare_digest(candidate, expected):
                return True
    return False


def parse_from_fields(from_raw: str) -> tuple[str, str]:
    name, email = split_from_address(from_raw)
    if not email:
        raise ResendInboundError("Could not parse sender email.")
    return (name, email)
