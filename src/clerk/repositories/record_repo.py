from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from clerk.repositories.models import ClientRecordRow


def _name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return local or "Client"


class RecordRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> ClientRecordRow | None:
        key = email.strip().lower()
        if not key:
            return None
        stmt = select(ClientRecordRow).where(ClientRecordRow.email == key)
        return self._session.scalar(stmt)

    def list_recent(self, limit: int = 100) -> list[ClientRecordRow]:
        stmt = select(ClientRecordRow).order_by(ClientRecordRow.updated_at.desc()).limit(limit)
        return list(self._session.scalars(stmt))

    def upsert(
        self,
        *,
        email: str,
        display_name: str,
        phone: str | None,
        last_channel: str,
        last_request: str,
        note: str,
        booking_day: str | None = None,
        booking_time: str | None = None,
        booking_state: str | None = None,
    ) -> ClientRecordRow:
        key = email.strip().lower()
        row = self.get_by_email(key)
        now = datetime.now(tz=UTC)
        name = display_name.strip()
        if row is None:
            row = ClientRecordRow(
                email=key,
                display_name=name or _name_from_email(key),
                phone=phone,
                last_channel=last_channel,
                last_request=last_request,
                note=note,
                booking_day=booking_day,
                booking_time=booking_time,
                booking_state=booking_state or "none",
                updated_at=now,
            )
            self._session.add(row)
        else:
            if name:
                row.display_name = name
            if phone:
                row.phone = phone
            row.last_channel = last_channel
            row.last_request = last_request
            row.note = note
            if booking_state is not None:
                row.booking_state = booking_state
                row.booking_day = booking_day
                row.booking_time = booking_time
            row.updated_at = now
        self._session.flush()
        return row

    def delete_demo_contacts(self, emails: set[str]) -> None:
        """Remove sample client files. Live addresses that are not demo contacts stay."""
        normalized = {email.strip().lower() for email in emails if email.strip()}
        filters = [ClientRecordRow.email.like("demo+%")]
        if normalized:
            filters.append(ClientRecordRow.email.in_(normalized))
        self._session.execute(delete(ClientRecordRow).where(or_(*filters)))
