import pytest

from clerk.schemas.agent import PolicyOutcomeKind, ProposalKind
from clerk.schemas.channel import display_channel, normalize_phone, outbound_channel_name
from clerk.services.records import (
    approval_note,
    booking_state_of,
    handling_note,
    rejection_note,
)


def test_channel_and_phone_edges() -> None:
    assert display_channel(None) == "Email"
    assert display_channel("web form") == "Web form"
    assert display_channel("x" * 40) == "x" * 32
    assert normalize_phone(None) is None
    assert normalize_phone("   ") is None
    assert normalize_phone("not-a-phone", strict=False) is None
    with pytest.raises(ValueError, match="phone number"):
        normalize_phone("not-a-phone")
    assert (
        outbound_channel_name(
            proposal_kind=ProposalKind.BOOKING_DRAFT,
            inbound_channel="WhatsApp",
        )
        == "whatsapp"
    )
    assert (
        outbound_channel_name(
            proposal_kind=ProposalKind.MISSING_FACT,
            inbound_channel="WhatsApp",
        )
        == "email"
    )


def test_record_notes_cover_empty_and_declined_cases() -> None:
    prepared = handling_note(
        proposal_kind=ProposalKind.BOOKING_DRAFT,
        outcome_kind=PolicyOutcomeKind.QUEUED,
        outcome_message="",
        auto_reply_text=None,
        booking_day=None,
        booking_time=None,
    )
    assert prepared == "Booking prepared. The slot is not held until you approve."

    email_note = handling_note(
        proposal_kind=ProposalKind.EMAIL_DRAFT,
        outcome_kind=PolicyOutcomeKind.QUEUED,
        outcome_message="",
        auto_reply_text=None,
        booking_day=None,
        booking_time=None,
    )
    assert email_note.startswith("Email draft")

    blocked = handling_note(
        proposal_kind=ProposalKind.EMAIL_DRAFT,
        outcome_kind=PolicyOutcomeKind.BLOCKED,
        outcome_message="Price R999 is not on the cited pages.",
        auto_reply_text=None,
        booking_day=None,
        booking_time=None,
    )
    assert blocked == "Price R999 is not on the cited pages."

    empty = handling_note(
        proposal_kind=ProposalKind.MISSING_FACT,
        outcome_kind=PolicyOutcomeKind.NEEDS_INFO,
        outcome_message="  ",
        auto_reply_text=None,
        booking_day=None,
        booking_time=None,
    )
    assert empty == "Record updated."

    agreed = handling_note(
        proposal_kind=ProposalKind.AUTO_REPLY,
        outcome_kind=PolicyOutcomeKind.SENT_AUTO,
        outcome_message="",
        auto_reply_text=None,
        booking_day=None,
        booking_time=None,
    )
    assert agreed == "Agreed reply sent."

    assert (
        approval_note(
            kind=ProposalKind.BOOKING_DRAFT.value,
            reply_channel="email",
            booking_day=None,
            booking_time=None,
        )
        == "Booking approved. The slot is now held."
    )
    assert approval_note(
        kind=ProposalKind.EMAIL_DRAFT.value,
        reply_channel="email",
        booking_day=None,
        booking_time=None,
    ).startswith("Email approved")
    assert "not held" in rejection_note(kind=ProposalKind.BOOKING_DRAFT.value).lower()
    assert "Nothing was sent" in rejection_note(kind=ProposalKind.WHATSAPP_DRAFT.value)
    assert rejection_note(kind=ProposalKind.EMAIL_DRAFT.value) == (
        "Draft declined. Nothing was sent."
    )
    assert booking_state_of("declined") == "declined"
    assert booking_state_of("other") == "none"
