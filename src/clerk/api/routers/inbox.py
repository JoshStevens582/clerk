from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.deps import ManagerDep, StaffDep
from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.models import InboundMessageRow
from clerk.repositories.record_repo import RecordRepository
from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.api import CreateInboundIn, InboundMessageOut
from clerk.schemas.auth import MessageOut
from clerk.services.demo_accounts import is_demo_staff
from clerk.services.inbox_seed import (
    demo_contact_emails,
    ensure_demo_inbox_samples,
    ordered_demo_samples,
)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _inbound_out(row: InboundMessageRow) -> InboundMessageOut:
    return InboundMessageOut(
        id=row.id,
        from_name=row.from_name,
        from_email=row.from_email,
        subject=row.subject,
        body=row.body,
        channel=row.channel,
        phone=row.phone,
        sample_id=row.sample_id,
        handled=row.task_id is not None,
        created_at=row.created_at,
    )


@router.get("", response_model=list[InboundMessageOut])
async def list_inbox(request: Request, staff: StaffDep) -> list[InboundMessageOut]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    settings = request.app.state.settings
    demo_desk = is_demo_staff(settings, staff.username)
    if demo_desk:
        ensure_demo_inbox_samples(db_factory)
    with db_factory() as session:
        repo = InboundRepository(session)
        rows = repo.list_open_demo_samples() if demo_desk else repo.list_open()
        if demo_desk:
            rows = ordered_demo_samples(rows)
        return [_inbound_out(row) for row in rows]


@router.post("", response_model=InboundMessageOut)
async def create_inbound(
    payload: CreateInboundIn,
    request: Request,
    staff: StaffDep,
) -> InboundMessageOut:
    settings = request.app.state.settings
    if is_demo_staff(settings, staff.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo desk is read-only for inbound mail.",
        )
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        row = InboundRepository(session).create(
            from_name=payload.from_name,
            from_email=payload.from_email,
            subject=payload.subject,
            body=payload.body,
            channel=payload.channel,
            phone=payload.phone,
        )
        session.commit()
        session.refresh(row)
        return _inbound_out(row)


@router.post("/clear-demo-mail", response_model=MessageOut)
async def clear_demo_mail(request: Request, staff: StaffDep) -> MessageOut:
    """Demo visitors only. Deletes sample sends and pending drafts, not live patient mail."""
    settings = request.app.state.settings
    if not is_demo_staff(settings, staff.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the demo desk can clear demo mail.",
        )
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        TaskRepository(session).clear_demo_mail()
        RecordRepository(session).delete_demo_contacts(demo_contact_emails())
        session.commit()
    return MessageOut(message="Demo mail cleared. Real patient mail was left in place.")


@router.post("/reset-demo", response_model=MessageOut)
async def reset_demo_inbox(request: Request, _: ManagerDep) -> MessageOut:
    """Put sample inbox rows back on the list (managers only, demo/training)."""
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        for row in InboundRepository(session).list_recent(limit=500):
            row.task_id = None
        session.commit()
    return MessageOut(message="Demo inbox restored. Open a message again from the left list.")
