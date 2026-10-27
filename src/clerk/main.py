import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from clerk.api.routers.auth import router as auth_router
from clerk.api.routers.health import router as health_router
from clerk.api.routers.samples import router as samples_router
from clerk.api.routers.tasks import router as tasks_router
from clerk.config import load_settings
from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.services.agent import ClerkAgentService
from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService
from clerk.services.rate_limit import InMemoryRateLimiter
from clerk.services.workflow import ClerkWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    Path("data").mkdir(exist_ok=True)

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    db_factory = session_factory(engine)
    page_store = PageStore(settings.pages_dir)
    policy = PolicyService(page_store)
    agent_service = ClerkAgentService(settings, page_store)
    workflow = ClerkWorkflow(agent_service, policy, db_factory)
    rate_limiter = InMemoryRateLimiter(settings, db_factory)

    app.state.settings = settings
    app.state.db_factory = db_factory
    app.state.page_store = page_store
    app.state.workflow = workflow
    app.state.rate_limiter = rate_limiter
    yield


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Clerk", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=False,
    )
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
    app.include_router(samples_router)
    app.include_router(tasks_router)
    return app


app = create_app()
