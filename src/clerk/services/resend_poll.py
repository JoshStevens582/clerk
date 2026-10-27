"""Poll Resend for received mail when a full-access API key is configured."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from clerk.services.resend_inbound import ResendApiAccess, list_received_email_ids
from clerk.services.resend_receive import ingest_resend_received_email

logger = logging.getLogger("clerk.resend_poll")

POLL_INTERVAL_SECONDS = 45


async def resend_inbound_poll_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        settings = app.state.settings
        access: ResendApiAccess = getattr(app.state, "resend_api_access", ResendApiAccess.NONE)
        if access != ResendApiAccess.FULL:
            continue
        try:
            email_ids = await list_received_email_ids(settings, limit=25)
        except Exception:
            logger.exception("resend receive poll failed")
            continue
        for email_id in email_ids:
            await ingest_resend_received_email(app, email_id=email_id)
