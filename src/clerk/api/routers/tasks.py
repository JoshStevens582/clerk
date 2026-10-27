from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from clerk.api.deps import StaffDep
from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.agent import PolicyOutcomeKind
from clerk.schemas.api import MessageIn, MessageOut, OutboxItemOut, QueueItemOut
from clerk.services.demo_accounts import is_demo_staff
from clerk.services.outbound_delivery import deliver_outbox_for_task
from clerk.services.pages import PageStore
from clerk.services.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from clerk.services.workflow import ClerkWorkflow

router = APIRouter(prefix="/api", tags=["tasks"])


def _client_key(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


@router.post("/messages", response_model=MessageOut)
async def submit_message(payload: MessageIn, request: Request, staff: StaffDep) -> MessageOut:
    settings = request.app.state.settings
    if is_demo_staff(settings, staff.username):
        db_factory: sessionmaker[Session] = request.app.state.db_factory
        if payload.inbound_id is not None:
            with db_factory() as session:
                from clerk.repositories.inbound_repo import InboundRepository

                inbound = InboundRepository(session).get(payload.inbound_id)
            if inbound is None or inbound.sample_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Demo desk can only run sample patient mail.",
                )
        elif payload.sample_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Demo desk can only run sample patient mail.",
            )
    workflow: ClerkWorkflow = request.app.state.workflow
    limiter: InMemoryRateLimiter | None = request.app.state.rate_limiter
    if limiter is not None:
        try:
            limiter.check_and_record(_client_key(request))
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=exc.message,
            ) from exc

    try:
        result = await workflow.handle_message(
            payload.text,
            sample_id=payload.sample_id,
            inbound_id=payload.inbound_id,
            reply_to_email=payload.reply_to_email,
            inbound_subject=payload.inbound_subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    demo = is_demo_staff(settings, staff.username)
    if result.outcome_kind == PolicyOutcomeKind.SENT_AUTO:
        await deliver_outbox_for_task(
            request.app.state.settings,
            request.app.state.db_factory,
            task_id=result.task_id,
            demo_dry_run=demo,
        )
    return MessageOut(
        task_id=result.task_id,
        outcome_kind=result.outcome_kind,
        message=result.message,
        auto_reply_text=result.auto_reply_text,
        queue_status=result.queue_status,
    )


@router.get("/queue", response_model=list[QueueItemOut])
async def list_queue(request: Request, staff: StaffDep) -> list[QueueItemOut]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    pages: PageStore = request.app.state.page_store
    settings = request.app.state.settings
    with db_factory() as session:
        repo = TaskRepository(session)
        demo_view = is_demo_staff(settings, staff.username)
        rows = repo.list_pending_demo() if demo_view else repo.list_pending()
        items: list[QueueItemOut] = []
        for row in rows:
            cited = TaskRepository.cited_pages(row)
            excerpts: dict[str, str] = {}
            for name in cited:
                try:
                    excerpts[name] = pages.read_page(name)
                except FileNotFoundError:
                    excerpts[name] = ""
            items.append(
                QueueItemOut(
                    id=row.id,
                    status=row.status,  # type: ignore[arg-type]
                    kind=row.kind,
                    inbound_text=row.inbound_text,
                    draft_subject=row.draft_subject,
                    draft_body=row.draft_body,
                    cited_pages=cited,
                    page_excerpts=excerpts,
                    slot_held=row.slot_held,
                    created_at=row.created_at,
                )
            )
        return items


@router.post("/queue/{task_id}/approve")
async def approve_task(task_id: int, request: Request, staff: StaffDep) -> dict[str, str]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    settings = request.app.state.settings
    demo = is_demo_staff(settings, staff.username)
    with db_factory() as session:
        repo = TaskRepository(session)
        if demo and not repo.is_demo_task(task_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Demo desk cannot approve live patient mail.",
            )
        row = repo.approve(task_id, resolved_by_username=staff.username)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if row.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task is not pending.",
            )
        session.commit()
    await deliver_outbox_for_task(
        settings,
        db_factory,
        task_id=task_id,
        demo_dry_run=demo,
    )
    return {"status": "approved"}


@router.post("/queue/{task_id}/reject")
async def reject_task(task_id: int, request: Request, staff: StaffDep) -> dict[str, str]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    settings = request.app.state.settings
    with db_factory() as session:
        repo = TaskRepository(session)
        if is_demo_staff(settings, staff.username) and not repo.is_demo_task(task_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Demo desk cannot change live patient mail.",
            )
        row = repo.reject(task_id, resolved_by_username=staff.username)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if row.status != "rejected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task is not pending.",
            )
        session.commit()
    return {"status": "rejected"}


@router.get("/outbox", response_model=list[OutboxItemOut])
async def list_outbox(request: Request, staff: StaffDep) -> list[OutboxItemOut]:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    settings = request.app.state.settings
    with db_factory() as session:
        repo = TaskRepository(session)
        demo_view = is_demo_staff(settings, staff.username)
        rows = repo.list_outbox_demo() if demo_view else repo.list_outbox()
        return [
            OutboxItemOut(
                id=row.id,
                kind=row.kind,
                subject=row.subject,
                body=row.body,
                to_email=row.to_email,
                delivered=row.delivered,
                delivery_error=row.delivery_error,
                sent_at=row.sent_at,
                source_task_id=row.source_task_id,
            )
            for row in rows
        ]
