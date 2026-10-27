"""Send approved and auto-replies to the patient via SMTP when configured."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.models import OutboxRow, TaskRow
from clerk.repositories.task_repo import TaskRepository
from clerk.services.smtp import send_plain_email

logger = logging.getLogger("clerk.outbound")


def smtp_configured(settings: Settings) -> bool:
    return bool(settings.smtp_host.strip()) and bool(
        settings.smtp_from.strip() or settings.smtp_username.strip()
    )


def _outbound_subject(task: TaskRow, outbox: OutboxRow) -> str:
    if outbox.subject and outbox.subject.strip():
        return outbox.subject.strip()
    if task.draft_subject and task.draft_subject.strip():
        return task.draft_subject.strip()
    if task.inbound_subject and task.inbound_subject.strip():
        return f"Re: {task.inbound_subject.strip()}"
    return "Message from Cape Town Physio"


def _latest_outbox(session: Session, task_id: int) -> OutboxRow | None:
    stmt = (
        select(OutboxRow)
        .where(OutboxRow.source_task_id == task_id)
        .order_by(OutboxRow.id.desc())
        .limit(1)
    )
    return session.scalar(stmt)


async def deliver_outbox_for_task(
    settings: Settings,
    db_factory: sessionmaker[Session],
    *,
    task_id: int,
) -> bool:
    """Try SMTP delivery for the newest outbox row on this task. Returns True if sent."""
    with db_factory() as session:
        task = TaskRepository(session).get(task_id)
        if task is None:
            return False
        outbox = _latest_outbox(session, task_id)
        if outbox is None:
            return False
        if outbox.delivered:
            return True
        to_email = (outbox.to_email or task.reply_to_email or "").strip()
        if not to_email:
            outbox.delivery_error = "No recipient email on this message."
            session.commit()
            return False
        subject = _outbound_subject(task, outbox)
        body = outbox.body
        outbox_id = outbox.id
        if not outbox.subject:
            outbox.subject = subject
        if not outbox.to_email:
            outbox.to_email = to_email.lower()
        session.commit()

    if not smtp_configured(settings):
        with db_factory() as session:
            outbox = session.get(OutboxRow, outbox_id)
            if outbox is not None:
                outbox.delivery_error = "SMTP is not configured; saved to outbox only."
                session.commit()
        return False

    sent, smtp_error = await send_plain_email(
        settings,
        to_address=to_email,
        subject=subject,
        body=body,
    )
    with db_factory() as session:
        outbox = session.get(OutboxRow, outbox_id)
        if outbox is None:
            return sent
        if sent:
            outbox.delivered = True
            outbox.delivery_error = None
            logger.info("outbound delivered task_id=%s to=%s", task_id, to_email)
        else:
            outbox.delivery_error = smtp_error or "SMTP send failed."
        session.commit()
    return sent
