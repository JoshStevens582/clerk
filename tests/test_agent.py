import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from clerk.config import Settings
from clerk.schemas.agent import ClerkRunResult, ProposalKind
from clerk.services.agent import SYSTEM_PROMPT, AgentDeps, ClerkAgentService
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
