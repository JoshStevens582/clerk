from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from clerk.schemas.agent import PolicyOutcomeKind, QueueStatus


class LoginIn(BaseModel):
    password: str


class LoginOut(BaseModel):
    ok: bool = True


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    sample_id: str | None = None


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
    pages_dir: str
    pending_count: int
