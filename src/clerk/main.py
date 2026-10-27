import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clerk.api.routers.auth import router as auth_router
from clerk.api.routers.health import router as health_router
from clerk.api.routers.hooks import router as hooks_router
from clerk.api.routers.inbox import router as inbox_router
from clerk.api.routers.samples import router as samples_router
from clerk.api.routers.staff import router as staff_router
from clerk.api.routers.tasks import router as tasks_router
from clerk.config import load_settings, require_secure_auth_secret
from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.services.agent import ClerkAgentService
from clerk.services.auth_rate_limit import AuthRateLimiter
from clerk.services.demo_accounts import ensure_demo_staff_users
from clerk.services.inbox_seed import ensure_demo_inbox_samples
from clerk.services.login_lockout import LoginLockout
from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService
from clerk.services.rate_limit import InMemoryRateLimiter
from clerk.services.redis_client import connect_redis
from clerk.services.resend_inbound import ResendApiAccess, probe_resend_api_access_sync
from clerk.services.resend_poll import resend_inbound_poll_loop
from clerk.services.staff_auth import bootstrap_staff_users
from clerk.services.workflow import ClerkWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    require_secure_auth_secret(settings)
    Path("data").mkdir(exist_ok=True)

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    db_factory = session_factory(engine)
    page_store = PageStore(settings.pages_dir)
    policy = PolicyService(page_store)
    agent_service = ClerkAgentService(settings, page_store)
    workflow = ClerkWorkflow(agent_service, policy, db_factory)
    rate_limiter = InMemoryRateLimiter(settings, db_factory)

    redis_client = await connect_redis(settings)
    auth_rate_limiter = (
        AuthRateLimiter(redis_client, settings)
        if redis_client is not None and settings.rate_limit_enabled
        else None
    )
    login_lockout = (
        LoginLockout(redis_client, settings)
        if redis_client is not None and settings.login_lockout_enabled
        else None
    )

    app.state.settings = settings
    app.state.db_factory = db_factory
    app.state.page_store = page_store
    app.state.workflow = workflow
    app.state.rate_limiter = rate_limiter
    app.state.auth_rate_limiter = auth_rate_limiter
    app.state.login_lockout = login_lockout
    app.state.redis_client = redis_client
    app.state.resend_api_access = probe_resend_api_access_sync(settings)
    poll_task: asyncio.Task[None] | None = None
    if app.state.resend_api_access == ResendApiAccess.FULL:
        poll_task = asyncio.create_task(resend_inbound_poll_loop(app))
    bootstrap_staff_users(settings, db_factory)
    ensure_demo_staff_users(settings, db_factory)
    if settings.clerk_seed_demo_inbox or settings.clerk_demo_users.strip():
        ensure_demo_inbox_samples(db_factory)
    yield
    if poll_task is not None:
        poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poll_task
    if redis_client is not None:
        await redis_client.aclose()


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Clerk", lifespan=lifespan)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(staff_router)
    app.include_router(samples_router)
    app.include_router(tasks_router)
    app.include_router(inbox_router)
    app.include_router(hooks_router)
    return app


app = create_app()
