from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clerk.repositories.models import InboundMessageRow


class InboundRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count(self) -> int:
        stmt = select(func.count()).select_from(InboundMessageRow)
        return int(self._session.scalar(stmt) or 0)

    def get(self, inbound_id: int) -> InboundMessageRow | None:
        return self._session.get(InboundMessageRow, inbound_id)

    def list_open(self) -> list[InboundMessageRow]:
        stmt = (
            select(InboundMessageRow)
            .where(InboundMessageRow.task_id.is_(None))
            .order_by(InboundMessageRow.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def list_recent(self, *, limit: int = 50) -> list[InboundMessageRow]:
        stmt = (
            select(InboundMessageRow)
            .order_by(InboundMessageRow.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def create(
        self,
        *,
        from_name: str,
        from_email: str,
        subject: str,
        body: str,
        channel: str = "Email",
        sample_id: str | None = None,
    ) -> InboundMessageRow:
        row = InboundMessageRow(
            from_name=from_name.strip(),
            from_email=from_email.strip().lower(),
            subject=subject.strip(),
            body=body.strip(),
            channel=channel.strip() or "Email",
            sample_id=sample_id.strip() if sample_id and sample_id.strip() else None,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def mark_handled(self, inbound_id: int, *, task_id: int) -> InboundMessageRow | None:
        row = self.get(inbound_id)
        if row is None:
            return None
        row.task_id = task_id
        self._session.flush()
        return row
