from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.task_repo import TaskRepository
from clerk.schemas.agent import PolicyOutcomeKind, QueueStatus
from clerk.services.agent import ClerkAgentService
from clerk.services.policy import PolicyService


class WorkflowResult:
    def __init__(
        self,
        *,
        task_id: int,
        outcome_kind: PolicyOutcomeKind,
        message: str,
        auto_reply_text: str | None,
        queue_status: QueueStatus | None,
    ) -> None:
        self.task_id = task_id
        self.outcome_kind = outcome_kind
        self.message = message
        self.auto_reply_text = auto_reply_text
        self.queue_status = queue_status


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
    ) -> WorkflowResult:
        resolved_sample_id = sample_id
        resolved_reply = reply_to_email
        resolved_subject = inbound_subject

        if inbound_id is not None:
            with self._db_factory() as session:
                inbound = InboundRepository(session).get(inbound_id)
                if inbound is None:
                    raise ValueError("Inbound message not found.")
                if inbound.task_id is not None:
                    raise ValueError("That inbound message was already handled.")
                if not resolved_sample_id and inbound.sample_id:
                    resolved_sample_id = inbound.sample_id
                if not resolved_reply:
                    resolved_reply = inbound.from_email
                if not resolved_subject:
                    resolved_subject = inbound.subject

        run_result = await self._agent.interpret(text, sample_id=resolved_sample_id)
        proposal = run_result.to_proposal(text)
        outcome = self._policy.apply(proposal)

        with self._db_factory() as session:
            repo = TaskRepository(session)
            row = repo.create_from_outcome(
                proposal_kind=proposal.kind,
                inbound_text=text,
                outcome=outcome,
                reply_to_email=resolved_reply,
                inbound_subject=resolved_subject,
                inbound_message_id=inbound_id,
            )
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
        )
