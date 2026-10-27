from clerk.schemas.agent import AgentProposal, PolicyOutcomeKind, ProposalKind
from clerk.services.policy import PolicyService


def test_agreed_reply_sends_itself(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.AUTO_REPLY,
        inbound_text="Do you have anything on Thursday?",
        auto_reply_id="after_hours_ack",
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.SENT_AUTO
    assert outcome.auto_reply_text == (
        "We got your message. We will reply on the next working day."
    )


def test_booking_waits_and_does_not_hold_slot(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.BOOKING_DRAFT,
        inbound_text="Book Thursday at 10:00",
        draft_subject="Booking request — Thursday 10:00",
        draft_body="Patient requested Thursday at 10:00. Session fee R650 per fees page.",
        cited_pages=["fees.md"],
        claimed_amounts=["R650"],
        booking_day="Thursday",
        booking_time="10:00",
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.QUEUED
    assert outcome.slot_held is False
    assert outcome.draft_body is not None
    assert "R650" in outcome.draft_body


def test_price_allowed_when_on_fees_page(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.BOOKING_DRAFT,
        inbound_text="Thursday 10:00 please",
        draft_subject="Booking",
        draft_body="Fee R650.",
        cited_pages=["fees.md"],
        claimed_amounts=["R650"],
        booking_day="Thursday",
        booking_time="10:00",
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.QUEUED


def test_invented_price_refused(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.BOOKING_DRAFT,
        inbound_text="Book me",
        draft_subject="Booking",
        draft_body="Fee R999.",
        cited_pages=["fees.md"],
        claimed_amounts=["R999"],
        booking_day="Thursday",
        booking_time="10:00",
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.BLOCKED
    assert outcome.block_reason == "invented_price"


def test_leave_days_must_match_page(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.EMAIL_DRAFT,
        inbound_text="Email HR that I want those days",
        draft_subject="Leave carry-over request",
        draft_body="Please record my request to use 5 days carry-over leave.",
        cited_pages=["leave-policy.md"],
        claimed_day_counts=["5 days"],
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.QUEUED


def test_invented_leave_days_refused(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.EMAIL_DRAFT,
        inbound_text="Email HR",
        draft_subject="Leave",
        draft_body="I want 10 days carry-over.",
        cited_pages=["leave-policy.md"],
        claimed_day_counts=["10 days"],
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.BLOCKED
    assert outcome.block_reason == "invented_leave_days"
