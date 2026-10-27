import pytest

from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.schemas.agent import PolicyOutcomeKind
from clerk.services.agent import ClerkAgentService
from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService
from clerk.services.workflow import ClerkWorkflow

PAGES = "pages"


@pytest.fixture
def workflow(tmp_path) -> ClerkWorkflow:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_db_engine(db_url)
    init_db(engine)
    factory = session_factory(engine)
    pages = PageStore(PAGES)
    settings = __import__("clerk.config", fromlist=["Settings"]).Settings(
        openai_api_key="",
        pages_dir=PAGES,
        database_url=db_url,
    )
    agent = ClerkAgentService(settings, pages)
    policy = PolicyService(pages)
    return ClerkWorkflow(agent, policy, factory)


@pytest.mark.asyncio
async def test_after_hours_auto_send(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Do you have anything on Thursday?",
        sample_id="after_hours_thursday",
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.auto_reply_text is not None


@pytest.mark.asyncio
async def test_booking_queues_without_slot(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Thursday 10:00",
        sample_id="booking_thursday_10",
    )
    assert result.outcome_kind == PolicyOutcomeKind.QUEUED
    assert result.queue_status == "pending"
