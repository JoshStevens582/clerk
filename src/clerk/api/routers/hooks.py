import secrets

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.models import InboundMessageRow
from clerk.schemas.api import CreateInboundIn, InboundMessageOut

router = APIRouter(prefix="/api/hooks", tags=["hooks"])


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


def _verify_webhook_secret(request: Request) -> None:
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
async def inbound_webhook(payload: CreateInboundIn, request: Request) -> InboundMessageOut:
    _verify_webhook_secret(request)
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        row = InboundRepository(session).create(
            from_name=payload.from_name,
            from_email=payload.from_email,
            subject=payload.subject,
            body=payload.body,
            channel=payload.channel,
        )
        session.commit()
        session.refresh(row)
        return _inbound_out(row)
