from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.api import HealthOut, LiveOut, ReadyOut

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/live", response_model=LiveOut)
async def live() -> LiveOut:
    return LiveOut()


@router.get("/ready", response_model=ReadyOut)
async def ready(request: Request, response: Response) -> ReadyOut:
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    database_ok = False
    try:
        with db_factory() as session:
            session.execute(text("SELECT 1"))
            database_ok = True
    except Exception:
        database_ok = False
    payload = ReadyOut(
        status="ok" if database_ok else "unavailable",
        database="ok" if database_ok else "unavailable",
    )
    if payload.status != "ok":
        response.status_code = 503
    return payload


@router.get("/health", response_model=HealthOut)
async def health(request: Request) -> HealthOut:
    settings = request.app.state.settings
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    with db_factory() as session:
        pending = TaskRepository(session).pending_count()
    return HealthOut(
        openai_configured=settings.openai_configured,
        pages_dir=settings.pages_dir,
        pending_count=pending,
    )
