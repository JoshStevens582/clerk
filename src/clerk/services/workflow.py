from typing import cast

from sqlalchemy.orm import Session, sessionmaker

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
    ) -> WorkflowResult:
        run_result = await self._agent.interpret(text, sample_id=sample_id)
        proposal = run_result.to_proposal(text)
        outcome = self._policy.apply(proposal)

        with self._db_factory() as session:
            repo = TaskRepository(session)
            row = repo.create_from_outcome(
                proposal_kind=proposal.kind,
                inbound_text=text,
                outcome=outcome,
            )
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
