"""Run Clerk on a stored inbound row (manual click or automatic email)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.schemas.agent import PolicyOutcomeKind
from clerk.services.outbound_delivery import deliver_outbox_for_task
from clerk.services.workflow import ClerkWorkflow

logger = logging.getLogger("clerk.inbound_processing")


async def run_clerk_on_inbound(app: FastAPI, *, inbound_id: int) -> None:
    settings = app.state.settings
    workflow: ClerkWorkflow = app.state.workflow
    db_factory: sessionmaker[Session] = app.state.db_factory

    with db_factory() as session:
        inbound = InboundRepository(session).get(inbound_id)
        if inbound is None or inbound.task_id is not None:
            return
        body = inbound.body
        from_email = inbound.from_email
        subject = inbound.subject
        sample_id = inbound.sample_id

    try:
        result = await workflow.handle_message(
            body,
            sample_id=sample_id,
            inbound_id=inbound_id,
            reply_to_email=from_email,
            inbound_subject=subject,
        )
    except ValueError as exc:
        logger.warning("inbound processing failed id=%s: %s", inbound_id, exc)
        return

    if result.outcome_kind == PolicyOutcomeKind.SENT_AUTO:
        await deliver_outbox_for_task(settings, db_factory, task_id=result.task_id)
    logger.info(
        "inbound processed id=%s task_id=%s outcome=%s",
        inbound_id,
        result.task_id,
        result.outcome_kind,
    )
