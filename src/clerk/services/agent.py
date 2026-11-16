from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from clerk.config import Settings
from clerk.schemas.agent import ClerkRunResult, ProposalKind
from clerk.services.demo_samples import result_for_sample
from clerk.services.pages import PageStore


@dataclass
class AgentDeps:
    pages: PageStore


SYSTEM_PROMPT = """You are Clerk, an automation agent for a small business.

Rules:
- If the customer only asks about availability after hours or needs a short acknowledgement,
  return kind=auto_reply with auto_reply_id=after_hours_ack. Do not book anything.
- If they ask to book and name a weekday and a time, return kind=booking_draft.
  Set booking_day to that weekday and booking_time to that time.
  Cite fees.md and hours.md. Put R650 in claimed_amounts only if fees.md contains it.
  Never set slot as held. A WhatsApp booking stays kind=booking_draft.
- If they ask what the session costs, return kind=auto_reply with auto_reply_id=session_fee.
- If they ask opening hours, what days you are open, or what times are available,
  return kind=auto_reply with auto_reply_id=opening_hours. Do not invent open slots.
- If they ask what you treat or what services you offer, return kind=auto_reply
  with auto_reply_id=services_offered.
- If they ask which documents a tax return needs, return kind=auto_reply
  with auto_reply_id=tax_documents. Do not draft your own list.
- If they ask to book but do not give both a weekday and a time, and they did not ask
  one of those questions, return kind=auto_reply with auto_reply_id=what_clerk_can_answer.
  Do not write your own wording.
- If the inbound channel is WhatsApp and they did not ask the fee, the hours, the services,
  or the tax documents, and they are not asking to book, return kind=whatsapp_draft.
  Cite page file names.
  Do not send it. Put a price in claimed_amounts only when that exact text is on the cited page.
- If they ask to email HR about leave carry-over, draft from leave-policy.md and put day counts
  in claimed_day_counts only when present on the page.
- Call list_pages, then read_page on the pages that could answer the question, before you draft.
- Only draft when a page you read states the answer. If no page covers the question, return
  kind=auto_reply with auto_reply_id=what_clerk_can_answer. Do not write your own wording.
  Never return a draft with empty cited_pages.
- Always cite page file names like fees.md in cited_pages when drafting.
"""


def build_agent(settings: Settings, pages: PageStore) -> Agent[AgentDeps, ClerkRunResult]:
    model_name = f"openai:{settings.openai_chat_model}"
    agent: Agent[AgentDeps, ClerkRunResult] = Agent(
        model_name,
        deps_type=AgentDeps,
        output_type=ClerkRunResult,
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.tool
    def read_page(ctx: RunContext[AgentDeps], page_name: str) -> str:
        """Read an approved markdown page by file name (for example fees.md)."""
        return ctx.deps.pages.read_page(page_name)

    @agent.tool
    def list_pages(ctx: RunContext[AgentDeps]) -> list[str]:
        """List markdown pages available in the pages directory."""
        return ctx.deps.pages.list_markdown_pages()

    return agent


class ClerkAgentService:
    def __init__(
        self,
        settings: Settings,
        pages: PageStore,
        agent: Agent[AgentDeps, ClerkRunResult] | None = None,
    ) -> None:
        self._agent: Agent[AgentDeps, ClerkRunResult] | None
        self._settings = settings
        self._pages = pages
        if agent is not None:
            self._agent = agent
        elif settings.openai_configured:
            self._agent = build_agent(settings, pages)
        else:
            self._agent = None

    async def interpret(
        self,
        text: str,
        *,
        sample_id: str | None = None,
        channel: str | None = None,
    ) -> ClerkRunResult:
        if sample_id:
            sample = result_for_sample(sample_id)
            if sample is not None:
                return sample

        if self._agent is None:
            return ClerkRunResult(
                kind=ProposalKind.MISSING_FACT,
                missing_fact_message=(
                    "OpenAI is not configured. Use a demo sample or set OPENAI_API_KEY."
                ),
            )

        prompt = text
        if channel and channel.strip().lower() == "whatsapp":
            prompt = f"Inbound channel: WhatsApp.\n\n{text}"
        deps = AgentDeps(pages=self._pages)
        run = await self._agent.run(prompt, deps=deps)
        return run.output
