from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.record_repo import RecordRepository
from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.agent import PolicyOutcomeKind, ProposalKind, QueueStatus
from clerk.schemas.api import ClientRecordOut
from clerk.schemas.channel import (
    display_channel,
    draft_kind_for_channel,
    normalize_phone,
    outbound_channel_name,
)
from clerk.services.agent import ClerkAgentService
from clerk.services.policy import PolicyService
from clerk.services.records import handling_note, to_client_record_out


class WorkflowResult:
    def __init__(
        self,
        *,
        task_id: int,
        outcome_kind: PolicyOutcomeKind,
        message: str,
        auto_reply_text: str | None,
        queue_status: QueueStatus | None,
        record: ClientRecordOut | None = None,
    ) -> None:
        self.task_id = task_id
        self.outcome_kind = outcome_kind
        self.message = message
        self.auto_reply_text = auto_reply_text
        self.queue_status = queue_status
        self.record = record


class ClerkWorkflow:
    def __init__(
        self,
        agent: ClerkAgentService,
        policy: PolicyService,
        db_factory: sessionmaker[Session],
    ) -> None:
        self._agent = agent
        self._policy = policy
        self._db_factory = db_factory

    async def handle_message(
        self,
        text: str,
        *,
        sample_id: str | None = None,
        inbound_id: int | None = None,
        reply_to_email: str | None = None,
        inbound_subject: str | None = None,
        from_name: str | None = None,
        channel: str | None = None,
        phone: str | None = None,
    ) -> WorkflowResult:
        resolved_sample_id = sample_id
        resolved_reply = reply_to_email
        resolved_subject = inbound_subject
        resolved_name = from_name.strip() if from_name and from_name.strip() else None
        resolved_channel = display_channel(channel)
        resolved_phone = normalize_phone(phone, strict=False)

        if inbound_id is not None:
            with self._db_factory() as session:
                inbound = InboundRepository(session).get(inbound_id)
                if inbound is None:
                    raise ValueError("Inbound message not found.")
                if inbound.task_id is not None:
                    raise ValueError("That inbound message was already handled.")
                if not resolved_sample_id and inbound.sample_id:
                    resolved_sample_id = inbound.sample_id
                resolved_reply = inbound.from_email
                if not resolved_subject:
                    resolved_subject = inbound.subject
                resolved_name = inbound.from_name
                resolved_channel = display_channel(inbound.channel)
                resolved_phone = normalize_phone(inbound.phone, strict=False)

        run_result = await self._agent.interpret(
            text,
            sample_id=resolved_sample_id,
            channel=resolved_channel,
        )
        proposal = run_result.to_proposal(text)
        proposal = proposal.model_copy(
            update={"kind": draft_kind_for_channel(proposal.kind, resolved_channel)}
        )
        outcome = self._policy.apply(proposal)
        reply_channel = outbound_channel_name(
            proposal_kind=proposal.kind,
            inbound_channel=resolved_channel,
        )
        booking_state = (
            "prepared"
            if outcome.kind == PolicyOutcomeKind.QUEUED
            and proposal.kind == ProposalKind.BOOKING_DRAFT
            else None
        )

        with self._db_factory() as session:
            repo = TaskRepository(session)
            row = repo.create_from_outcome(
                proposal_kind=proposal.kind,
                inbound_text=text,
                outcome=outcome,
                reply_to_email=resolved_reply,
                reply_channel=reply_channel,
                reply_phone=resolved_phone,
                booking_day=proposal.booking_day,
                booking_time=proposal.booking_time,
                inbound_subject=resolved_subject,
                inbound_message_id=inbound_id,
            )
            record: ClientRecordOut | None = None
            contact_email = (resolved_reply or "").strip()
            if contact_email:
                record_row = RecordRepository(session).upsert(
                    email=contact_email,
                    display_name=resolved_name or "",
                    phone=resolved_phone,
                    last_channel=resolved_channel,
                    last_request=text,
                    note=handling_note(
                        proposal_kind=proposal.kind,
                        outcome_kind=outcome.kind,
                        outcome_message=outcome.message,
                        auto_reply_text=outcome.auto_reply_text,
                        booking_day=proposal.booking_day,
                        booking_time=proposal.booking_time,
                    ),
                    booking_day=proposal.booking_day if booking_state else None,
                    booking_time=proposal.booking_time if booking_state else None,
                    booking_state=booking_state,
                )
                record = to_client_record_out(record_row)
            if inbound_id is not None:
                InboundRepository(session).mark_handled(inbound_id, task_id=row.id)
            session.commit()
            queue_status = cast(QueueStatus, row.status)
            task_id = row.id

        return WorkflowResult(
            task_id=task_id,
            outcome_kind=outcome.kind,
            message=outcome.message,
            auto_reply_text=outcome.auto_reply_text,
            queue_status=queue_status,
            record=record,
        )
