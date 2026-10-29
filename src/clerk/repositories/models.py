from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clerk.repositories.db import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class StaffUserRow(Base):
    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="staff")
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    mfa_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    mfa_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PasswordResetTokenRow(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff_users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RefreshSessionRow(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff_users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MfaRecoveryCodeRow(Base):
    __tablename__ = "mfa_recovery_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff_users.id", ondelete="CASCADE"),
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class InboundMessageRow(Base):
    __tablename__ = "inbound_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_name: Mapped[str] = mapped_column(String(128))
    from_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(32), default="Email")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sample_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    inbound_text: Mapped[str] = mapped_column(Text)
    inbound_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbound_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reply_to_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reply_channel: Mapped[str] = mapped_column(String(32), default="email")
    reply_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    booking_day: Mapped[str | None] = mapped_column(String(64), nullable=True)
    booking_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    draft_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_pages_json: Mapped[str] = mapped_column(Text, default="[]")
    slot_held: Mapped[bool] = mapped_column(default=False)
    auto_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_username: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutboxRow(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    to_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="email")
    to_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivered: Mapped[bool] = mapped_column(default=False)
    delivery_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ClientRecordRow(Base):
    """Client file Clerk writes when it handles a message."""

    __tablename__ = "client_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_channel: Mapped[str] = mapped_column(String(32), default="Email")
    last_request: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    booking_day: Mapped[str | None] = mapped_column(String(64), nullable=True)
    booking_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    booking_state: Mapped[str] = mapped_column(String(16), default="none")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DailyUsageRow(Base):
    __tablename__ = "daily_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usage_date: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
