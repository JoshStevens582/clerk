"""Resend receiving: webhook metadata + API fetch for body."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
from enum import StrEnum
from typing import Any

import httpx

from clerk.config import Settings
from clerk.services.email_address import split_from_address

logger = logging.getLogger("clerk.resend_inbound")

RESEND_API_BASE = "https://api.resend.com"


class ResendApiAccess(StrEnum):
    NONE = "none"
    SEND_ONLY = "send_only"
    FULL = "full"


class ResendInboundError(Exception):
    pass


def effective_resend_api_key(settings: Settings) -> str:
    explicit = settings.resend_api_key.strip()
    if explicit:
        return explicit
    if settings.smtp_host.strip() == "smtp.resend.com":
        return settings.smtp_password.strip()
    return ""


def resend_webhook_configured(settings: Settings) -> bool:
    return bool(settings.resend_webhook_secret.strip())


def probe_resend_api_access_sync(settings: Settings) -> ResendApiAccess:
    """Classify the configured Resend key (send-only keys cannot fetch received mail)."""
    api_key = effective_resend_api_key(settings)
    if not api_key:
        return ResendApiAccess.NONE
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"{RESEND_API_BASE}/emails/receiving",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"limit": 1},
            )
    except httpx.HTTPError:
        logger.warning("Resend API probe failed (network).")
        return ResendApiAccess.NONE
    if response.status_code == 401:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if payload.get("name") == "restricted_api_key":
            return ResendApiAccess.SEND_ONLY
        return ResendApiAccess.NONE
    if response.status_code >= 400:
        return ResendApiAccess.NONE
    return ResendApiAccess.FULL


def inbound_automation_ready(settings: Settings, *, resend_api_access: ResendApiAccess) -> bool:
    """True when Clerk can pull received mail from Resend (full-access key + address)."""
    if resend_api_access != ResendApiAccess.FULL:
        return False
    return bool(settings.clerk_inbound_address.strip())


async def list_received_email_ids(settings: Settings, *, limit: int = 25) -> list[str]:
    api_key = effective_resend_api_key(settings)
    if not api_key:
        return []
    capped = max(1, min(limit, 100))
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{RESEND_API_BASE}/emails/receiving",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": capped},
        )
    if response.status_code >= 400:
        raise ResendInboundError(f"Resend list receiving failed ({response.status_code}).")
    payload: dict[str, Any] = response.json()
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            email_id = row.get("id")
            if isinstance(email_id, str) and email_id.strip():
                ids.append(email_id.strip())
    return ids


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
