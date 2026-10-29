"""Wording written onto the client record. Persistence lives in the repository."""

from sqlalchemy.orm import Session

from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.models import ClientRecordRow, TaskRow
from clerk.repositories.record_repo import RecordRepository
from clerk.schemas.agent import PolicyOutcomeKind, ProposalKind
from clerk.schemas.api import BookingState, ClientRecordOut
from clerk.schemas.channel import display_channel


def handling_note(
    *,
    proposal_kind: ProposalKind,
    outcome_kind: PolicyOutcomeKind,
    outcome_message: str,
    auto_reply_text: str | None,
    booking_day: str | None,
    booking_time: str | None,
) -> str:
    if outcome_kind == PolicyOutcomeKind.SENT_AUTO:
        text = (auto_reply_text or outcome_message).strip()
        return f"Agreed reply sent: {text}" if text else "Agreed reply sent."
    if outcome_kind == PolicyOutcomeKind.QUEUED and proposal_kind == ProposalKind.BOOKING_DRAFT:
        when = " ".join(part for part in (booking_day, booking_time) if part)
        if when:
            return f"Booking prepared for {when}. The slot is not held until you approve."
        return "Booking prepared. The slot is not held until you approve."
    if outcome_kind == PolicyOutcomeKind.QUEUED and proposal_kind == ProposalKind.WHATSAPP_DRAFT:
        return "WhatsApp draft written from the cited pages. Not sent. Waiting for approval."
    if outcome_kind == PolicyOutcomeKind.QUEUED and proposal_kind == ProposalKind.EMAIL_DRAFT:
        return "Email draft written from the cited pages. Not sent. Waiting for approval."
    if outcome_message.strip():
        return outcome_message.strip()
    return "Record updated."


def approval_note(
    *,
    kind: str,
    reply_channel: str,
    booking_day: str | None,
    booking_time: str | None,
) -> str:
    if kind == ProposalKind.BOOKING_DRAFT.value:
        when = " ".join(part for part in (booking_day, booking_time) if part)
        if when:
            return f"Booking approved. {when} is now held."
        return "Booking approved. The slot is now held."
    if reply_channel == "whatsapp" or kind == ProposalKind.WHATSAPP_DRAFT.value:
        return "WhatsApp approved and placed in the outbox. It was not sent to a phone."
    return "Email approved and placed in the outbox."


def rejection_note(*, kind: str) -> str:
    if kind == ProposalKind.BOOKING_DRAFT.value:
        return "Booking declined. The slot was not held and nothing was sent."
    if kind == ProposalKind.WHATSAPP_DRAFT.value:
        return "WhatsApp draft declined. Nothing was sent."
    return "Draft declined. Nothing was sent."


def booking_state_of(value: str) -> BookingState:
    if value == "prepared":
        return "prepared"
    if value == "held":
        return "held"
    if value == "declined":
        return "declined"
    return "none"


def apply_task_decision(
    session: Session,
    task: TaskRow,
    *,
    approved: bool,
) -> ClientRecordOut | None:
    display_name = ""
    phone = task.reply_phone
    if task.inbound_message_id is not None:
        inbound = InboundRepository(session).get(task.inbound_message_id)
        if inbound is not None:
            display_name = inbound.from_name
            phone = phone or inbound.phone
    return write_decision(
        session,
        task,
        approved=approved,
        display_name=display_name,
        phone=phone,
    )


def write_decision(
    session: Session,
    task: TaskRow,
    *,
    approved: bool,
    display_name: str = "",
    phone: str | None = None,
) -> ClientRecordOut | None:
    """Update the client file after the owner approves or rejects a draft."""
    email = (task.reply_to_email or "").strip()
    if not email:
        return None
    existing = RecordRepository(session).get_by_email(email)
    last_channel = existing.last_channel if existing is not None else display_channel(
        "WhatsApp" if task.reply_channel == "whatsapp" else "Email"
    )
    booking_state: str | None = None
    if task.kind == ProposalKind.BOOKING_DRAFT.value:
        booking_state = "held" if approved else "declined"
    note = (
        approval_note(
            kind=task.kind,
            reply_channel=task.reply_channel,
            booking_day=task.booking_day,
            booking_time=task.booking_time,
        )
        if approved
        else rejection_note(kind=task.kind)
    )
    row = RecordRepository(session).upsert(
        email=email,
        display_name=display_name,
        phone=phone or task.reply_phone,
        last_channel=last_channel,
        last_request=task.inbound_text,
        note=note,
        booking_day=task.booking_day if booking_state else None,
        booking_time=task.booking_time if booking_state else None,
        booking_state=booking_state,
    )
    return to_client_record_out(row)


def to_client_record_out(row: ClientRecordRow) -> ClientRecordOut:
    return ClientRecordOut(
        id=row.id,
        display_name=row.display_name,
        email=row.email,
        phone=row.phone,
        last_channel=row.last_channel,
        last_request=row.last_request,
        note=row.note,
        booking_day=row.booking_day,
        booking_time=row.booking_time,
        booking_state=booking_state_of(row.booking_state),
        updated_at=row.updated_at,
    )
