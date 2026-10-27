from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.api import HealthOut, LiveOut, ReadyOut
from clerk.services.outbound_delivery import smtp_configured
from clerk.services.resend_inbound import (
    ResendApiAccess,
    inbound_automation_ready,
    resend_webhook_configured,
)

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


def _inbound_setup_note(settings: Settings, access: ResendApiAccess) -> str:
    if access == ResendApiAccess.SEND_ONLY:
        return (
            "Resend API key is send-only. Create a Full access key, set RESEND_API_KEY on the "
            "server, and forward domain mail into Resend (see docs/launch-inbound.md)."
        )
    if access == ResendApiAccess.NONE:
        if not effective_resend_key_configured(settings):
            return "Set RESEND_API_KEY (full access) on the server for automatic inbound mail."
        return "Resend API key could not list received mail. Check RESEND_API_KEY on the server."
    if not settings.clerk_inbound_address.strip():
        return "Set CLERK_INBOUND_ADDRESS to the address patients email."
    return (
        "Forward clerk@ to your @….resend.app address in domains.co.za Email Only Hosting "
        "(cPanel → Forwarders). See docs/launch-inbound.md."
    )


def effective_resend_key_configured(settings: Settings) -> bool:
    from clerk.services.resend_inbound import effective_resend_api_key

    return bool(effective_resend_api_key(settings))


@router.get("/health", response_model=HealthOut)
async def health(request: Request) -> HealthOut:
    settings = request.app.state.settings
    db_factory: sessionmaker[Session] = request.app.state.db_factory
    access: ResendApiAccess = getattr(
        request.app.state, "resend_api_access", ResendApiAccess.NONE
    )
    with db_factory() as session:
        pending = TaskRepository(session).pending_count()
    full_access = access == ResendApiAccess.FULL
    webhook = resend_webhook_configured(settings)
    automation_ready = inbound_automation_ready(settings, resend_api_access=access)
    note = ""
    if not automation_ready:
        note = _inbound_setup_note(settings, access)
    elif not webhook:
        note = (
            "Polling Resend for new mail (webhook optional). Ensure patient mail reaches Resend."
        )
    return HealthOut(
        openai_configured=settings.openai_configured,
        smtp_configured=smtp_configured(settings),
        inbound_automation_ready=automation_ready,
        inbound_resend_api_full_access=full_access,
        inbound_webhook_configured=webhook,
        inbound_setup_note=note,
        inbound_address=settings.clerk_inbound_address.strip(),
        pages_dir=settings.pages_dir,
        pending_count=pending,
    )
