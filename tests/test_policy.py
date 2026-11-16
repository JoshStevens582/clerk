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
    assert outcome.kind == PolicyOutcomeKind.SENT_AUTO
    assert outcome.block_reason == "invented_price"
    assert outcome.auto_reply_text == (
        "Ask one of these and I will answer: What is the session fee? "
        "What are your opening hours? What do you treat? "
        "What documents do you need for a tax return? "
        "To book, tell me the day and the time, for example Tuesday at 10. "
        "A person replies to anything else."
    )


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


def test_two_approved_questions_send_both_sentences(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.AUTO_REPLY,
        inbound_text="What is the session fee and what are your opening hours?",
        auto_reply_id="session_fee",
        auto_reply_ids=["session_fee", "opening_hours"],
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.SENT_AUTO
    assert outcome.auto_reply_text is not None
    assert "R650" in outcome.auto_reply_text
    assert "Monday to Friday" in outcome.auto_reply_text
    assert "\n\n" in outcome.auto_reply_text


def test_whatsapp_draft_waits_for_approval(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.WHATSAPP_DRAFT,
        inbound_text="Please WhatsApp me the standard session fee.",
        draft_body="The standard session fee is R650, from the fees page.",
        cited_pages=["fees.md"],
        claimed_amounts=["R650"],
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.QUEUED
    assert outcome.slot_held is False
    assert outcome.message == "Nothing has been sent yet. Press Approve."


def test_whatsapp_invented_price_refused(policy: PolicyService) -> None:
    proposal = AgentProposal(
        kind=ProposalKind.WHATSAPP_DRAFT,
        inbound_text="WhatsApp me the fee",
        draft_body="The fee is R999.",
        cited_pages=["fees.md"],
        claimed_amounts=["R999"],
    )
    outcome = policy.apply(proposal)
    assert outcome.kind == PolicyOutcomeKind.SENT_AUTO
    assert outcome.block_reason == "invented_price"
    assert outcome.auto_reply_text is not None
    assert "R999" not in outcome.auto_reply_text


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
    assert outcome.kind == PolicyOutcomeKind.SENT_AUTO
    assert outcome.block_reason == "invented_leave_days"
    assert outcome.auto_reply_text is not None
    assert "10 days" not in outcome.auto_reply_text
