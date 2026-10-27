"""Ingest a Resend email.received event into Clerk."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.inbound_repo import InboundRepository
from clerk.services.inbound_processing import run_clerk_on_inbound
from clerk.services.resend_inbound import (
    ResendInboundError,
    fetch_received_email_body,
    parse_from_fields,
)

logger = logging.getLogger("clerk.resend_receive")


async def ingest_resend_received_email(app: FastAPI, *, email_id: str) -> None:
    settings: Settings = app.state.settings
    db_factory: sessionmaker[Session] = app.state.db_factory

    with db_factory() as session:
        existing = InboundRepository(session).get_by_external_id(email_id)
        if existing is not None:
            if existing.task_id is None:
                await run_clerk_on_inbound(app, inbound_id=existing.id)
            return

    try:
        from_raw, subject, body = await fetch_received_email_body(settings, email_id=email_id)
        from_name, from_email = parse_from_fields(from_raw)
    except ResendInboundError as exc:
        logger.warning("resend ingest failed email_id=%s: %s", email_id, exc)
        return

    with db_factory() as session:
        row = InboundRepository(session).create(
            from_name=from_name,
            from_email=from_email,
            subject=subject,
            body=body,
            channel="Email",
            source="resend",
            external_id=email_id,
        )
        session.commit()
        inbound_id = row.id

    await run_clerk_on_inbound(app, inbound_id=inbound_id)
