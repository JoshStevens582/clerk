import json
from datetime import UTC, datetime

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from clerk.repositories.models import InboundMessageRow, OutboxRow, TaskRow
from clerk.schemas.agent import PolicyOutcome, PolicyOutcomeKind, ProposalKind, QueueStatus

_PENDING_BOOKING_DISCLAIMER = "Time not held until approved."
_APPROVED_BOOKING_HELD = "This appointment time is now held for you."


def outbound_body_after_approval(*, kind: str, draft_body: str) -> str:
    """Patient-facing text after a manager approves (draft is written for the queue state)."""
    if kind != "booking_draft":
        return draft_body
    if _PENDING_BOOKING_DISCLAIMER in draft_body:
        return draft_body.replace(_PENDING_BOOKING_DISCLAIMER, _APPROVED_BOOKING_HELD)
    trimmed = draft_body.rstrip()
    if not trimmed:
        return _APPROVED_BOOKING_HELD
    return f"{trimmed}\n\n{_APPROVED_BOOKING_HELD}"


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_from_outcome(
        self,
        *,
        proposal_kind: ProposalKind,
        inbound_text: str,
        outcome: PolicyOutcome,
        reply_to_email: str | None = None,
        reply_channel: str = "email",
        reply_phone: str | None = None,
        booking_day: str | None = None,
        booking_time: str | None = None,
        inbound_subject: str | None = None,
        inbound_message_id: int | None = None,
    ) -> TaskRow:
        status: QueueStatus
        if outcome.kind == PolicyOutcomeKind.SENT_AUTO:
            status = "sent_auto"
        elif outcome.kind == PolicyOutcomeKind.QUEUED:
            status = "pending"
        else:
            status = "rejected"

        row = TaskRow(
            status=status,
            kind=proposal_kind.value,
            inbound_text=inbound_text,
            inbound_message_id=inbound_message_id,
            inbound_subject=inbound_subject,
            reply_to_email=reply_to_email.strip().lower() if reply_to_email else None,
            reply_channel=reply_channel if reply_channel in {"email", "whatsapp"} else "email",
            reply_phone=reply_phone.strip() if reply_phone and reply_phone.strip() else None,
            booking_day=booking_day,
            booking_time=booking_time,
            draft_subject=outcome.draft_subject,
            draft_body=outcome.draft_body,
            cited_pages_json=json.dumps(outcome.cited_pages),
            slot_held=outcome.slot_held,
            auto_reply_text=outcome.auto_reply_text,
            block_reason=outcome.block_reason,
            outcome_message=outcome.message,
        )
        self._session.add(row)
        self._session.flush()

        if outcome.kind == PolicyOutcomeKind.SENT_AUTO and outcome.auto_reply_text:
            self._add_outbox(
                kind="auto_reply",
                subject=None,
                body=outcome.auto_reply_text,
                source_task_id=row.id,
                to_email=row.reply_to_email,
                channel=row.reply_channel,
                to_phone=row.reply_phone if row.reply_channel == "whatsapp" else None,
            )
            row.resolved_at = datetime.now(tz=UTC)
        return row

    def list_pending(self) -> list[TaskRow]:
        stmt = (
            select(TaskRow)
            .where(TaskRow.status == "pending")
            .order_by(TaskRow.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def list_pending_demo(self) -> list[TaskRow]:
        stmt = (
            select(TaskRow)
            .outerjoin(InboundMessageRow, TaskRow.inbound_message_id == InboundMessageRow.id)
            .where(
                TaskRow.status == "pending",
                or_(
                    TaskRow.inbound_message_id.is_(None),
                    InboundMessageRow.sample_id.is_not(None),
                ),
            )
            .order_by(TaskRow.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def is_demo_task(self, task_id: int) -> bool:
        row = self.get(task_id)
        if row is None:
            return False
        if row.inbound_message_id is None:
            return True
        inbound = self._session.get(InboundMessageRow, row.inbound_message_id)
        return inbound is not None and inbound.sample_id is not None

    def list_outbox_demo(self, limit: int = 50) -> list[OutboxRow]:
        stmt = (
            select(OutboxRow)
            .join(TaskRow, OutboxRow.source_task_id == TaskRow.id)
            .outerjoin(InboundMessageRow, TaskRow.inbound_message_id == InboundMessageRow.id)
            .where(
                or_(
                    TaskRow.inbound_message_id.is_(None),
                    InboundMessageRow.sample_id.is_not(None),
                )
            )
            .order_by(OutboxRow.sent_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def get(self, task_id: int) -> TaskRow | None:
        return self._session.get(TaskRow, task_id)

    def approve(self, task_id: int, *, resolved_by_username: str | None = None) -> TaskRow | None:
        row = self.get(task_id)
        if row is None or row.status != "pending":
            return row
        row.status = "approved"
        row.slot_held = True
        row.resolved_at = datetime.now(tz=UTC)
        row.resolved_by_username = resolved_by_username
        send_body = outbound_body_after_approval(
            kind=row.kind,
            draft_body=row.draft_body or "",
        )
        row.draft_body = send_body
        self._add_outbox(
            kind=row.kind,
            subject=row.draft_subject,
            body=send_body,
            source_task_id=row.id,
            to_email=row.reply_to_email,
            channel=row.reply_channel,
            to_phone=row.reply_phone if row.reply_channel == "whatsapp" else None,
        )
        return row

    def reject(self, task_id: int, *, resolved_by_username: str | None = None) -> TaskRow | None:
        row = self.get(task_id)
        if row is None or row.status != "pending":
            return row
        row.status = "rejected"
        row.resolved_at = datetime.now(tz=UTC)
        row.resolved_by_username = resolved_by_username
        return row

    def clear_demo_mail(self) -> None:
        """Remove demo outbox rows and pending demo drafts. Live patient mail stays."""
        demo_task_ids = list(self._session.scalars(self._demo_task_id_query()))
        if not demo_task_ids:
            return
        self._session.execute(
            delete(OutboxRow).where(OutboxRow.source_task_id.in_(demo_task_ids))
        )
        self._session.execute(
            delete(TaskRow).where(
                TaskRow.id.in_(demo_task_ids),
                TaskRow.status == "pending",
            )
        )

    def _demo_task_id_query(self) -> Select[int]:
        return (
            select(TaskRow.id)
            .outerjoin(InboundMessageRow, TaskRow.inbound_message_id == InboundMessageRow.id)
            .where(
                or_(
                    TaskRow.inbound_message_id.is_(None),
                    InboundMessageRow.sample_id.is_not(None),
                )
            )
        )

    def list_outbox(self, limit: int = 50) -> list[OutboxRow]:
        stmt = select(OutboxRow).order_by(OutboxRow.sent_at.desc()).limit(limit)
        return list(self._session.scalars(stmt))

    def pending_count(self) -> int:
        stmt = select(func.count()).select_from(TaskRow).where(TaskRow.status == "pending")
        return int(self._session.scalar(stmt) or 0)

    def _add_outbox(
        self,
        *,
        kind: str,
        subject: str | None,
        body: str,
        source_task_id: int,
        to_email: str | None = None,
        channel: str = "email",
        to_phone: str | None = None,
    ) -> OutboxRow:
        row = OutboxRow(
            kind=kind,
            subject=subject,
            body=body,
            to_email=to_email.strip().lower() if to_email else None,
            channel=channel if channel in {"email", "whatsapp"} else "email",
            to_phone=to_phone.strip() if to_phone and to_phone.strip() else None,
            source_task_id=source_task_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    @staticmethod
    def cited_pages(row: TaskRow) -> list[str]:
        try:
            parsed = json.loads(row.cited_pages_json)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return []
