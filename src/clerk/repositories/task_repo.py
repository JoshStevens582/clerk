import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clerk.repositories.models import OutboxRow, TaskRow
from clerk.schemas.agent import PolicyOutcome, PolicyOutcomeKind, ProposalKind, QueueStatus


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
        self._add_outbox(
            kind=row.kind,
            subject=row.draft_subject,
            body=row.draft_body or "",
            source_task_id=row.id,
            to_email=row.reply_to_email,
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
    ) -> OutboxRow:
        row = OutboxRow(
            kind=kind,
            subject=subject,
            body=body,
            to_email=to_email.strip().lower() if to_email else None,
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
