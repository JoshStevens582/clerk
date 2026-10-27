import threading
import time
from collections import defaultdict, deque
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from clerk.config import Settings
from clerk.repositories.models import DailyUsageRow


class RateLimitExceeded(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InMemoryRateLimiter:
    """Per-client minute window plus SQLite-backed daily counters."""

    def __init__(
        self,
        settings: Settings,
        db_factory: sessionmaker[Session],
    ) -> None:
        self._settings = settings
        self._db_factory = db_factory
        self._lock = threading.Lock()
        self._minute_hits: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, client_key: str) -> None:
        if not self._settings.rate_limit_enabled:
            return
        now = time.time()
        with self._lock:
            window = self._minute_hits[client_key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self._settings.rate_limit_per_minute:
                msg = "Too many requests. Try again in a minute."
                raise RateLimitExceeded(msg)
            window.append(now)

        self._check_daily(client_key)

    def _check_daily(self, client_key: str) -> None:
        today = date.today().isoformat()
        with self._db_factory() as session:
            global_row = self._get_or_create(session, f"global:{today}")
            client_row = self._get_or_create(session, f"client:{client_key}:{today}")
            if global_row.request_count >= self._settings.rate_limit_global_per_day:
                msg = "Daily demo limit reached. Try again tomorrow."
                raise RateLimitExceeded(msg)
            if client_row.request_count >= self._settings.rate_limit_per_day:
                msg = "Your daily limit is reached. Try again tomorrow."
                raise RateLimitExceeded(msg)
            global_row.request_count += 1
            client_row.request_count += 1
            session.commit()

    @staticmethod
    def _get_or_create(session: Session, usage_date: str) -> DailyUsageRow:
        stmt = select(DailyUsageRow).where(DailyUsageRow.usage_date == usage_date)
        row = session.scalar(stmt)
        if row is None:
            row = DailyUsageRow(usage_date=usage_date, request_count=0)
            session.add(row)
            session.flush()
        return row
