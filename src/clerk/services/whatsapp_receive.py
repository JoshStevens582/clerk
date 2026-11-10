"""Store WhatsApp text messages from the Cloud API webhook and run Clerk on them."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.services.inbound_processing import run_clerk_on_inbound
from clerk.services.whatsapp import InboundWhatsAppText

logger = logging.getLogger("clerk.whatsapp_receive")

_MAX_BODY_LENGTH = 8000


def store_inbound_whatsapp(
    db_factory: sessionmaker[Session], messages: list[InboundWhatsAppText]
) -> list[int]:
    """Save new messages. A message id Meta already delivered is not stored twice."""
    created: list[int] = []
    with db_factory() as session:
        repo = InboundRepository(session)
        for message in messages:
            external_id = f"wa:{message.message_id}"
            if repo.get_by_external_id(external_id) is not None:
                continue
            row = repo.create(
                from_name=message.name or message.phone,
                from_email="",
                subject="WhatsApp message",
                body=message.text[:_MAX_BODY_LENGTH],
                channel="WhatsApp",
                phone=message.phone,
                source="whatsapp",
                external_id=external_id,
            )
            created.append(row.id)
        session.commit()
    return created


async def run_clerk_on_whatsapp(app: FastAPI, *, inbound_ids: list[int]) -> None:
    for inbound_id in inbound_ids:
        await run_clerk_on_inbound(app, inbound_id=inbound_id)
    if inbound_ids:
        logger.info("whatsapp inbound processed count=%s", len(inbound_ids))
