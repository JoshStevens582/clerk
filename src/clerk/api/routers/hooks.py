import json
import logging
import secrets
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.models import InboundMessageRow
from clerk.schemas.api import CreateInboundIn, InboundMessageOut
from clerk.schemas.auth import MessageOut
from clerk.services.inbound_processing import run_clerk_on_inbound
from clerk.services.resend_inbound import verify_svix_signature
from clerk.services.resend_receive import ingest_resend_received_email

router = APIRouter(prefix="/api/hooks", tags=["hooks"])
logger = logging.getLogger("clerk.hooks")


def _inbound_out(row: InboundMessageRow) -> InboundMessageOut:
    return InboundMessageOut(
        id=row.id,
        from_name=row.from_name,
        from_email=row.from_email,
        subject=row.subject,
        body=row.body,
        channel=row.channel,
        sample_id=row.sample_id,
        handled=row.task_id is not None,
        created_at=row.created_at,
    )


def _verify_custom_webhook_secret(request: Request) -> None:
    settings = request.app.state.settings
    expected = settings.clerk_inbound_webhook_secret.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inbound webhook is not configured.",
        )
    provided = request.headers.get("x-clerk-inbound-secret", "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )


@router.post("/inbound", response_model=InboundMessageOut)
async def inbound_webhook(
    payload: CreateInboundIn,
    request: Request,
    background_tasks: BackgroundTasks,
) -> InboundMessageOut:
    _verify_custom_webhook_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        row = InboundRepository(session).create(
            from_name=payload.from_name,
            from_email=payload.from_email,
            subject=payload.subject,
            body=payload.body,
            channel=payload.channel,
            source="hook",
        )
        session.commit()
        session.refresh(row)
        inbound_id = row.id
    background_tasks.add_task(run_clerk_on_inbound, request.app, inbound_id=inbound_id)
    return _inbound_out(row)


@router.post("/resend")
async def resend_inbound_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, bool]:
    """Resend `email.received` — configure in Resend dashboard."""
    settings = request.app.state.settings
    body = await request.body()
    secret = settings.resend_webhook_secret.strip()
    if secret:
        msg_id = request.headers.get("svix-id", "")
        timestamp = request.headers.get("svix-timestamp", "")
        signature = request.headers.get("svix-signature", "")
        if not verify_svix_signature(
            body=body,
            secret=secret,
            msg_id=msg_id,
            timestamp=timestamp,
            signature_header=signature,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature.",
            )
    try:
        event: dict[str, Any] = json.loads(body.decode())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON.",
        ) from exc

    if event.get("type") != "email.received":
        return {"ok": True}

    data = event.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing event data.")
    email_id = data.get("email_id")
    if not isinstance(email_id, str) or not email_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing email_id.")

    background_tasks.add_task(ingest_resend_received_email, request.app, email_id=email_id.strip())
    logger.info("resend webhook queued email_id=%s", email_id)
    return {"ok": True}


@router.get("/resend/health", response_model=MessageOut)
async def resend_hook_health() -> MessageOut:
    return MessageOut(message="Resend webhook endpoint is reachable.")
