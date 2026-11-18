import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from clerk.config import Settings
from clerk.schemas.agent import ClerkRunResult, ProposalKind
from clerk.services.agent import (
    SYSTEM_PROMPT,
    AgentDeps,
    ClerkAgentService,
    read_page_for_model,
)
from clerk.services.demo_samples import result_for_sample
from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService


@pytest.mark.parametrize(
    ("sample_id", "expected_kind"),
    [
        ("after_hours_thursday", ProposalKind.AUTO_REPLY),
        ("booking_thursday_10", ProposalKind.BOOKING_DRAFT),
        ("tax_return_email", ProposalKind.EMAIL_DRAFT),
        ("leave_hr_email", ProposalKind.EMAIL_DRAFT),
        ("whatsapp_session_fee", ProposalKind.WHATSAPP_DRAFT),
    ],
)
def test_demo_samples_match_plan(sample_id: str, expected_kind: ProposalKind) -> None:
    result = result_for_sample(sample_id)
    assert result is not None
    assert result.kind == expected_kind


@pytest.mark.asyncio
async def test_agent_output_passes_policy_with_fake_model() -> None:
    pages = PageStore("pages")
    settings = Settings(pages_dir="pages")
    structured = ClerkRunResult(
        kind=ProposalKind.BOOKING_DRAFT,
        draft_subject="Booking",
        draft_body="Fee R650.",
        cited_pages=["fees.md"],
        claimed_amounts=["R650"],
        booking_day="Thursday",
        booking_time="10:00",
    )
    test_model = TestModel(call_tools=[], custom_output_args=structured.model_dump())
    agent: Agent[AgentDeps, ClerkRunResult] = Agent(
        test_model,
        deps_type=AgentDeps,
        output_type=ClerkRunResult,
        system_prompt=SYSTEM_PROMPT,
    )
    service = ClerkAgentService(settings, pages, agent=agent)
    run = await service.interpret("Book Thursday at 10")
    policy = PolicyService(pages)
    outcome = policy.apply(run.to_proposal("Book Thursday at 10"))
    assert outcome.kind.value == "queued"


@pytest.mark.asyncio
async def test_configured_model_answers_a_demo_sample() -> None:
    pages = PageStore("pages")
    settings = Settings(pages_dir="pages", openai_api_key="")
    structured = ClerkRunResult(
        kind=ProposalKind.WHATSAPP_DRAFT,
        draft_body="From the model.",
        cited_pages=["fees.md"],
    )
    test_model = TestModel(call_tools=[], custom_output_args=structured.model_dump())
    agent: Agent[AgentDeps, ClerkRunResult] = Agent(
        test_model,
        deps_type=AgentDeps,
        output_type=ClerkRunResult,
        system_prompt=SYSTEM_PROMPT,
    )
    service = ClerkAgentService(settings, pages, agent=agent)
    run = await service.interpret(
        "Please WhatsApp me the standard session fee.",
        sample_id="whatsapp_session_fee",
        channel="WhatsApp",
    )
    assert run.draft_body == "From the model."
    assert run.kind == ProposalKind.WHATSAPP_DRAFT


def test_missing_page_tells_the_model_instead_of_crashing() -> None:
    pages = PageStore("pages")
    text = read_page_for_model(pages, "what_clerk_can_answer")
    assert "No page named what_clerk_can_answer" in text
    assert "fees.md" in text
    assert "R650" in read_page_for_model(pages, "fees.md")


@pytest.mark.asyncio
async def test_model_crash_sends_the_stored_limit() -> None:
    pages = PageStore("pages")
    settings = Settings(pages_dir="pages", openai_api_key="")

    class BrokenAgent:
        async def run(self, prompt: str, deps: AgentDeps) -> object:
            del prompt, deps
            raise FileNotFoundError("Page not found: what_clerk_can_answer")

    service = ClerkAgentService(settings, pages)
    service._agent = BrokenAgent()  # type: ignore[assignment]
    run = await service.interpret("What can you help me with?", channel="WhatsApp")
    assert run.kind == ProposalKind.AUTO_REPLY
    assert run.auto_reply_id == "what_clerk_can_answer"


@pytest.mark.asyncio
async def test_saved_sample_when_model_is_missing() -> None:
    pages = PageStore("pages")
    settings = Settings(pages_dir="pages", openai_api_key="")
    service = ClerkAgentService(settings, pages)
    run = await service.interpret(
        "Please book me for Thursday at 10:00.",
        sample_id="booking_thursday_10",
    )
    assert run.kind == ProposalKind.BOOKING_DRAFT
    assert run.booking_time == "10:00"
