from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from clerk.schemas.agent import PolicyOutcomeKind, QueueStatus


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    sample_id: str | None = None
    inbound_id: int | None = None
    reply_to_email: str | None = Field(default=None, max_length=320)
    inbound_subject: str | None = Field(default=None, max_length=512)


class InboundMessageOut(BaseModel):
    id: int
    from_name: str
    from_email: str
    subject: str
    body: str
    channel: str
    sample_id: str | None = None
    handled: bool
    created_at: datetime


class CreateInboundIn(BaseModel):
    from_name: str = Field(min_length=1, max_length=128)
    from_email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=512)
    body: str = Field(min_length=1, max_length=8000)
    channel: str = Field(default="Email", max_length=32)


class MessageOut(BaseModel):
    task_id: int
    outcome_kind: PolicyOutcomeKind
    message: str
    auto_reply_text: str | None = None
    queue_status: QueueStatus | None = None


class QueueItemOut(BaseModel):
    id: int
    status: QueueStatus
    kind: str
    inbound_text: str
    draft_subject: str | None
    draft_body: str | None
    cited_pages: list[str]
    page_excerpts: dict[str, str]
    slot_held: bool
    created_at: datetime


class OutboxItemOut(BaseModel):
    id: int
    kind: str
    subject: str | None
    body: str
    to_email: str | None = None
    delivered: bool = False
    delivery_error: str | None = None
    sent_at: datetime
    source_task_id: int | None


class LiveOut(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyOut(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    openai_configured: bool
    smtp_configured: bool
    inbound_automation_ready: bool
    inbound_resend_api_full_access: bool
    inbound_webhook_configured: bool
    inbound_setup_note: str
    inbound_address: str
    pages_dir: str
    pending_count: int
