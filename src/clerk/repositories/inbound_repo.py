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

    def get_by_external_id(self, external_id: str) -> InboundMessageRow | None:
        normalized = external_id.strip()
        if not normalized:
            return None
        stmt = select(InboundMessageRow).where(InboundMessageRow.external_id == normalized)
        return self._session.scalar(stmt)

    def list_open(self) -> list[InboundMessageRow]:
        stmt = (
            select(InboundMessageRow)
            .where(InboundMessageRow.task_id.is_(None))
            .order_by(InboundMessageRow.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def list_open_demo_samples(self) -> list[InboundMessageRow]:
        """One unhandled row per sample, newest id first within each sample."""
        stmt = (
            select(InboundMessageRow)
            .where(
                InboundMessageRow.task_id.is_(None),
                InboundMessageRow.sample_id.is_not(None),
            )
            .order_by(InboundMessageRow.id.desc())
        )
        seen_sample_ids: set[str] = set()
        chosen: list[InboundMessageRow] = []
        for row in self._session.scalars(stmt):
            sample_id = row.sample_id
            if not sample_id or sample_id in seen_sample_ids:
                continue
            seen_sample_ids.add(sample_id)
            chosen.append(row)
        return chosen

    def has_open_sample(self, sample_id: str) -> bool:
        normalized = sample_id.strip()
        if not normalized:
            return False
        stmt = (
            select(InboundMessageRow.id)
            .where(
                InboundMessageRow.sample_id == normalized,
                InboundMessageRow.task_id.is_(None),
            )
            .limit(1)
        )
        return self._session.scalar(stmt) is not None

    def get_by_sample_id(self, sample_id: str) -> InboundMessageRow | None:
        normalized = sample_id.strip()
        if not normalized:
            return None
        stmt = (
            select(InboundMessageRow)
            .where(InboundMessageRow.sample_id == normalized)
            .limit(1)
        )
        return self._session.scalar(stmt)

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
        phone: str | None = None,
        sample_id: str | None = None,
        source: str = "manual",
        external_id: str | None = None,
    ) -> InboundMessageRow:
        ext = external_id.strip() if external_id and external_id.strip() else None
        row = InboundMessageRow(
            from_name=from_name.strip(),
            from_email=from_email.strip().lower(),
            subject=subject.strip(),
            body=body.strip(),
            channel=channel.strip() or "Email",
            phone=phone.strip() if phone and phone.strip() else None,
            sample_id=sample_id.strip() if sample_id and sample_id.strip() else None,
            source=source.strip() or "manual",
            external_id=ext,
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
