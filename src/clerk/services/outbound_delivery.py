"""Send approved and auto-replies to the patient by email (SMTP) or WhatsApp when configured."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.models import OutboxRow, TaskRow
from clerk.repositories.task_repo import TaskRepository
from clerk.services.smtp import send_plain_email
from clerk.services.whatsapp import send_whatsapp_text, whatsapp_send_configured

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


def _record_delivery(
    db_factory: sessionmaker[Session],
    outbox_id: int,
    *,
    delivered: bool,
    error: str | None,
) -> None:
    with db_factory() as session:
        outbox = session.get(OutboxRow, outbox_id)
        if outbox is None:
            return
        outbox.delivered = delivered
        outbox.delivery_error = error
        session.commit()


async def _deliver_whatsapp(
    settings: Settings,
    db_factory: sessionmaker[Session],
    *,
    task_id: int,
    outbox_id: int,
    to_phone: str,
    body: str,
    demo_dry_run: bool,
) -> bool:
    if demo_dry_run:
        _record_delivery(
            db_factory, outbox_id, delivered=True, error="Demo desk. Not sent on WhatsApp."
        )
        return True
    if not to_phone:
        _record_delivery(
            db_factory, outbox_id, delivered=False, error="No phone number on this message."
        )
        return False
    if not whatsapp_send_configured(settings):
        _record_delivery(
            db_factory,
            outbox_id,
            delivered=False,
            error=(
                "WhatsApp is not connected. Saved to the outbox only. "
                "Nothing was sent to a phone."
            ),
        )
        return False
    sent, error = await send_whatsapp_text(settings, to_phone=to_phone, body=body)
    _record_delivery(
        db_factory,
        outbox_id,
        delivered=sent,
        error=None if sent else (error or "WhatsApp send failed."),
    )
    if sent:
        logger.info("outbound whatsapp delivered task_id=%s", task_id)
    return sent


async def _deliver_email(
    settings: Settings,
    db_factory: sessionmaker[Session],
    *,
    task_id: int,
    outbox_id: int,
    to_email: str,
    subject: str,
    body: str,
    demo_dry_run: bool,
) -> bool:
    if demo_dry_run:
        _record_delivery(
            db_factory,
            outbox_id,
            delivered=True,
            error="Demo desk — not emailed to a real patient.",
        )
        logger.info("outbound demo dry-run task_id=%s to=%s", task_id, to_email)
        return True
    if not smtp_configured(settings):
        _record_delivery(
            db_factory,
            outbox_id,
            delivered=False,
            error="SMTP is not configured; saved to outbox only.",
        )
        return False
    sent, smtp_error = await send_plain_email(
        settings,
        to_address=to_email,
        subject=subject,
        body=body,
    )
    _record_delivery(
        db_factory,
        outbox_id,
        delivered=sent,
        error=None if sent else (smtp_error or "SMTP send failed."),
    )
    if sent:
        logger.info("outbound delivered task_id=%s to=%s", task_id, to_email)
    return sent


async def deliver_outbox_for_task(
    settings: Settings,
    db_factory: sessionmaker[Session],
    *,
    task_id: int,
    demo_dry_run: bool = False,
) -> bool:
    """Deliver the newest outbox row on this task by email or WhatsApp. True if sent."""
    with db_factory() as session:
        task = TaskRepository(session).get(task_id)
        if task is None:
            return False
        outbox = _latest_outbox(session, task_id)
        if outbox is None:
            return False
        if outbox.delivered:
            return True
        outbox_id = outbox.id
        body = outbox.body
        if (outbox.channel or "email").strip().lower() == "whatsapp":
            to_phone = (outbox.to_phone or task.reply_phone or "").strip()
            if to_phone and not outbox.to_phone:
                outbox.to_phone = to_phone
                session.commit()
            is_whatsapp = True
            to_email = ""
            subject = ""
        else:
            is_whatsapp = False
            to_phone = ""
            to_email = (outbox.to_email or task.reply_to_email or "").strip()
            if not to_email:
                outbox.delivery_error = "No recipient email on this message."
                session.commit()
                return False
            subject = _outbound_subject(task, outbox)
            if not outbox.subject:
                outbox.subject = subject
            if not outbox.to_email:
                outbox.to_email = to_email.lower()
            session.commit()

    if is_whatsapp:
        return await _deliver_whatsapp(
            settings,
            db_factory,
            task_id=task_id,
            outbox_id=outbox_id,
            to_phone=to_phone,
            body=body,
            demo_dry_run=demo_dry_run,
        )
    return await _deliver_email(
        settings,
        db_factory,
        task_id=task_id,
        outbox_id=outbox_id,
        to_email=to_email,
        subject=subject,
        body=body,
        demo_dry_run=demo_dry_run,
    )
