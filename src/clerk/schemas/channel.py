"""Inbound channel names and which outbox channel a proposal uses."""

import re

from clerk.schemas.agent import ProposalKind

_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{6,20}$")


def display_channel(raw: str | None) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        return "Email"
    lowered = cleaned.lower()
    if lowered == "email":
        return "Email"
    if lowered == "whatsapp":
        return "WhatsApp"
    if lowered == "web form":
        return "Web form"
    return cleaned[:32]


def is_whatsapp_channel(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "whatsapp"


def normalize_phone(raw: str | None, *, strict: bool = True) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if _PHONE_RE.fullmatch(cleaned) is None:
        if strict:
            raise ValueError("Enter a phone number with digits, spaces, or a leading +.")
        return None
    return cleaned


def draft_kind_for_channel(kind: ProposalKind, inbound_channel: str | None) -> ProposalKind:
    """A reply on WhatsApp is a WhatsApp draft, even if the model picked email."""
    if kind == ProposalKind.EMAIL_DRAFT and is_whatsapp_channel(inbound_channel):
        return ProposalKind.WHATSAPP_DRAFT
    return kind


def outbound_channel_name(*, proposal_kind: ProposalKind, inbound_channel: str | None) -> str:
    """Stored on the task and outbox: 'email' or 'whatsapp'."""
    if proposal_kind == ProposalKind.WHATSAPP_DRAFT:
        return "whatsapp"
    if is_whatsapp_channel(inbound_channel) and proposal_kind in {
        ProposalKind.AUTO_REPLY,
        ProposalKind.EMAIL_DRAFT,
        ProposalKind.BOOKING_DRAFT,
    }:
        return "whatsapp"
    return "email"
