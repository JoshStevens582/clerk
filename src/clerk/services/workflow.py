import re
from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.record_repo import RecordRepository
from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.agent import AgentProposal, PolicyOutcomeKind, ProposalKind, QueueStatus
from clerk.schemas.api import ClientRecordOut
from clerk.schemas.channel import (
    display_channel,
    draft_kind_for_channel,
    normalize_phone,
    outbound_channel_name,
)
from clerk.services.agent import ClerkAgentService
from clerk.services.policy import PolicyService
from clerk.services.records import handling_note, to_client_record_out

_ANSWERED_OUTCOMES = {PolicyOutcomeKind.QUEUED, PolicyOutcomeKind.SENT_AUTO}


_BOOKING_ASK = re.compile(r"\b(?:book|booking|appointment)\b", re.IGNORECASE)
_APPROVED_QUESTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("session_fee", re.compile(r"\b(?:fees?|costs?|prices?|how much)\b", re.IGNORECASE)),
    (
        "opening_hours",
        re.compile(
            r"\b(?:opening hours|business hours|are you open|when are you open|"
            r"when do you (?:open|close)|closing time|what times?|what days?|"
            r"availability|times are available|days are available)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "services_offered",
        re.compile(
            r"\b(?:what do you (?:treat|offer)|what services|services do you|"
            r"do you treat|sports injury)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "tax_documents",
        re.compile(r"\b(?:tax return|tax documents|irp5|it3)\b", re.IGNORECASE),
    ),
)
_WEEKDAY = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
_CLOCK = re.compile(
    r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b"
    r"|\b(\d{1,2}):(\d{2})\s*(am|pm)?\b"
    r"|\b(\d{1,2})\s*(am|pm)\b",
    re.IGNORECASE,
)


def _asks_to_book(text: str) -> bool:
    return _BOOKING_ASK.search(text) is not None


def _format_clock(hour: int, minute: int, meridiem: str | None) -> str | None:
    if not 0 <= minute <= 59:
        return None
    marker = (meridiem or "").lower()
    if marker in {"am", "pm"}:
        if not 1 <= hour <= 12:
            return None
        suffix = "AM" if marker == "am" else "PM"
        return f"{hour}:{minute:02d} {suffix}"
    if not 0 <= hour <= 23:
        return None
    return f"{hour}:{minute:02d}"


def _clock_from_match(match: re.Match[str]) -> str | None:
    if match.group(1) is not None:
        hour = int(match.group(1))
        minute = int(match.group(2) or "0")
        meridiem = match.group(3)
    elif match.group(4) is not None:
        hour = int(match.group(4))
        minute = int(match.group(5) or "0")
        meridiem = match.group(6)
    else:
        hour = int(match.group(7) or "0")
        minute = 0
        meridiem = match.group(8)
    return _format_clock(hour, minute, meridiem)


def _slot_from_text(text: str) -> tuple[str, str] | None:
    """Weekday and clock written by the customer. The model does not get to drop them."""
    day_match = _WEEKDAY.search(text)
    if day_match is None:
        return None
    for clock_match in _CLOCK.finditer(text):
        clock = _clock_from_match(clock_match)
        if clock is not None:
            return day_match.group(1).title(), clock
    return None


def _queued_booking(proposal: AgentProposal, day: str, clock: str) -> AgentProposal:
    """Draft only the fee and hours from the pages, plus the day and time they named."""
    return proposal.model_copy(
        update={
            "kind": ProposalKind.BOOKING_DRAFT,
            "auto_reply_id": None,
            "draft_subject": f"Booking request — {day} {clock}",
            "draft_body": (
                f"You asked for {day} at {clock}. "
                "A standard session is R650. "
                "We are open Monday to Friday and close at 5:00 PM. "
                "Time not held until approved."
            ),
            "cited_pages": ["fees.md", "hours.md"],
            "claimed_amounts": ["R650"],
            "claimed_day_counts": [],
            "booking_day": day,
            "booking_time": clock,
            "missing_fact_message": None,
        }
    )


def _approved_question_ids(text: str) -> list[str]:
    return [reply_id for reply_id, pattern in _APPROVED_QUESTIONS if pattern.search(text)]


def _stored_auto_reply(proposal: AgentProposal, reply_ids: list[str]) -> AgentProposal:
    """Send the exact stored sentences. The model does not write them."""
    return proposal.model_copy(
        update={
            "kind": ProposalKind.AUTO_REPLY,
            "auto_reply_id": reply_ids[0],
            "auto_reply_ids": reply_ids,
            "draft_subject": None,
            "draft_body": None,
            "cited_pages": [],
            "claimed_amounts": [],
            "claimed_day_counts": [],
            "booking_day": None,
            "booking_time": None,
            "missing_fact_message": None,
        }
    )


def _repair_incomplete_booking(
    proposal: AgentProposal,
    *,
    answer_questions: bool,
) -> AgentProposal:
    """A named day and time waits for approval. Approved questions send their stored answer."""
    text = proposal.inbound_text
    if _asks_to_book(text):
        day = (proposal.booking_day or "").strip()
        clock = (proposal.booking_time or "").strip()
        has_slot = bool(day and clock)
        has_draft = bool(proposal.cited_pages and (proposal.draft_body or "").strip())
        if has_slot and has_draft:
            return proposal
        named_slot = _slot_from_text(text)
        if named_slot is not None:
            return _queued_booking(proposal, named_slot[0], named_slot[1])
    if answer_questions:
        question_ids = _approved_question_ids(text)
        if question_ids:
            return _stored_auto_reply(proposal, question_ids)
    if _asks_to_book(text):
        return _stored_auto_reply(proposal, ["what_clerk_can_answer"])
    return proposal


def unanswered_note(kind: PolicyOutcomeKind, message: str) -> str:
    """Inbox note for a message Clerk could not answer from the pages."""
    if kind == PolicyOutcomeKind.NEEDS_INFO:
        return f"Clerk could not answer from your pages: {message}"
    return f"Clerk stopped its draft: {message}"


class WorkflowResult:
    def __init__(
        self,
        *,
        task_id: int,
        outcome_kind: PolicyOutcomeKind,
        message: str,
        auto_reply_text: str | None,
        queue_status: QueueStatus | None,
        record: ClientRecordOut | None = None,
    ) -> None:
        self.task_id = task_id
        self.outcome_kind = outcome_kind
        self.message = message
        self.auto_reply_text = auto_reply_text
        self.queue_status = queue_status
        self.record = record


class ClerkWorkflow:
    def __init__(
        self,
        agent: ClerkAgentService,
        policy: PolicyService,
        db_factory: sessionmaker[Session],
    ) -> None:
        self._agent = agent
        self._policy = policy
        self._db_factory = db_factory

    async def handle_message(
        self,
        text: str,
        *,
        sample_id: str | None = None,
        inbound_id: int | None = None,
        reply_to_email: str | None = None,
        inbound_subject: str | None = None,
        from_name: str | None = None,
        channel: str | None = None,
        phone: str | None = None,
    ) -> WorkflowResult:
        resolved_sample_id = sample_id
        resolved_reply = reply_to_email
        resolved_subject = inbound_subject
        resolved_name = from_name.strip() if from_name and from_name.strip() else None
        resolved_channel = display_channel(channel)
        resolved_phone = normalize_phone(phone, strict=False)
        inbound_is_sample = False

        if inbound_id is not None:
            with self._db_factory() as session:
                inbound = InboundRepository(session).get(inbound_id)
                if inbound is None:
                    raise ValueError("Inbound message not found.")
                if inbound.task_id is not None:
                    raise ValueError("That inbound message was already handled.")
                if not resolved_sample_id and inbound.sample_id:
                    resolved_sample_id = inbound.sample_id
                resolved_reply = inbound.from_email
                if not resolved_subject:
                    resolved_subject = inbound.subject
                resolved_name = inbound.from_name
                resolved_channel = display_channel(inbound.channel)
                resolved_phone = normalize_phone(inbound.phone, strict=False)
                inbound_is_sample = inbound.sample_id is not None

        run_result = await self._agent.interpret(
            text,
            sample_id=resolved_sample_id,
            channel=resolved_channel,
        )
        proposal = run_result.to_proposal(text)
        proposal = proposal.model_copy(
            update={"kind": draft_kind_for_channel(proposal.kind, resolved_channel)}
        )
        proposal = _repair_incomplete_booking(
            proposal,
            answer_questions=resolved_sample_id is None and not inbound_is_sample,
        )
        outcome = self._policy.apply(proposal)
        reply_channel = outbound_channel_name(
            proposal_kind=proposal.kind,
            inbound_channel=resolved_channel,
        )
        booking_state = (
            "prepared"
            if outcome.kind == PolicyOutcomeKind.QUEUED
            and proposal.kind == ProposalKind.BOOKING_DRAFT
            else None
        )

        with self._db_factory() as session:
            repo = TaskRepository(session)
            row = repo.create_from_outcome(
                proposal_kind=proposal.kind,
                inbound_text=text,
                outcome=outcome,
                reply_to_email=resolved_reply,
                reply_channel=reply_channel,
                reply_phone=resolved_phone,
                booking_day=proposal.booking_day,
                booking_time=proposal.booking_time,
                inbound_subject=resolved_subject,
                inbound_message_id=inbound_id,
            )
            record: ClientRecordOut | None = None
            contact_email = (resolved_reply or "").strip()
            if contact_email:
                record_row = RecordRepository(session).upsert(
                    email=contact_email,
                    display_name=resolved_name or "",
                    phone=resolved_phone,
                    last_channel=resolved_channel,
                    last_request=text,
                    note=handling_note(
                        proposal_kind=proposal.kind,
                        outcome_kind=outcome.kind,
                        outcome_message=outcome.message,
                        auto_reply_text=outcome.auto_reply_text,
                        booking_day=proposal.booking_day,
                        booking_time=proposal.booking_time,
                    ),
                    booking_day=proposal.booking_day if booking_state else None,
                    booking_time=proposal.booking_time if booking_state else None,
                    booking_state=booking_state,
                )
                record = to_client_record_out(record_row)
            if inbound_id is not None:
                inbound_repo = InboundRepository(session)
                if inbound_is_sample or outcome.kind in _ANSWERED_OUTCOMES:
                    inbound_repo.mark_handled(inbound_id, task_id=row.id)
                else:
                    inbound_repo.keep_open_with_note(
                        inbound_id, note=unanswered_note(outcome.kind, outcome.message)
                    )
            session.commit()
            queue_status = cast(QueueStatus, row.status)
            task_id = row.id

        return WorkflowResult(
            task_id=task_id,
            outcome_kind=outcome.kind,
            message=outcome.message,
            auto_reply_text=outcome.auto_reply_text,
            queue_status=queue_status,
            record=record,
        )
