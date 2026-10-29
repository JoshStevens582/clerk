from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ProposalKind(StrEnum):
    AUTO_REPLY = "auto_reply"
    BOOKING_DRAFT = "booking_draft"
    EMAIL_DRAFT = "email_draft"
    WHATSAPP_DRAFT = "whatsapp_draft"
    MISSING_FACT = "missing_fact"


class AgentProposal(BaseModel):
    """Structured intent from the agent (or tests) before policy runs."""

    kind: ProposalKind
    inbound_text: str = ""
    auto_reply_id: str | None = None
    draft_subject: str | None = None
    draft_body: str | None = None
    cited_pages: list[str] = Field(default_factory=list)
    claimed_amounts: list[str] = Field(default_factory=list)
    claimed_day_counts: list[str] = Field(default_factory=list)
    booking_day: str | None = None
    booking_time: str | None = None
    missing_fact_message: str | None = None


class PolicyOutcomeKind(StrEnum):
    SENT_AUTO = "sent_auto"
    QUEUED = "queued"
    BLOCKED = "blocked"
    NEEDS_INFO = "needs_info"


class PolicyOutcome(BaseModel):
    kind: PolicyOutcomeKind
    message: str
    auto_reply_text: str | None = None
    draft_subject: str | None = None
    draft_body: str | None = None
    cited_pages: list[str] = Field(default_factory=list)
    slot_held: bool = False
    block_reason: str | None = None


class ClerkRunResult(BaseModel):
    """Final structured output from the Pydantic AI agent."""

    kind: ProposalKind
    auto_reply_id: str | None = None
    draft_subject: str | None = None
    draft_body: str | None = None
    cited_pages: list[str] = Field(default_factory=list)
    claimed_amounts: list[str] = Field(default_factory=list)
    claimed_day_counts: list[str] = Field(default_factory=list)
    booking_day: str | None = None
    booking_time: str | None = None
    missing_fact_message: str | None = None

    def to_proposal(self, inbound_text: str) -> AgentProposal:
        return AgentProposal(
            kind=self.kind,
            inbound_text=inbound_text,
            auto_reply_id=self.auto_reply_id,
            draft_subject=self.draft_subject,
            draft_body=self.draft_body,
            cited_pages=list(self.cited_pages),
            claimed_amounts=list(self.claimed_amounts),
            claimed_day_counts=list(self.claimed_day_counts),
            booking_day=self.booking_day,
            booking_time=self.booking_time,
            missing_fact_message=self.missing_fact_message,
        )


QueueStatus = Literal["pending", "approved", "rejected", "sent_auto"]
