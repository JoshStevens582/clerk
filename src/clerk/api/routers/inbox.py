from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.deps import StaffDep, require_staff
from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.models import InboundMessageRow
from clerk.schemas.api import CreateInboundIn, InboundMessageOut

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


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


@router.get("", response_model=list[InboundMessageOut], dependencies=[Depends(require_staff)])
async def list_inbox(request: Request) -> list[InboundMessageOut]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        rows = InboundRepository(session).list_open()
        return [_inbound_out(row) for row in rows]


@router.post("", response_model=InboundMessageOut, dependencies=[Depends(require_staff)])
async def create_inbound(
    payload: CreateInboundIn,
    request: Request,
    _: StaffDep,
) -> InboundMessageOut:
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
