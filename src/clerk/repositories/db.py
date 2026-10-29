from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        Path("data").mkdir(exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    from clerk.repositories import models  # noqa: F401

    Base.metadata.create_all(engine)
    _apply_sqlite_migrations(engine)


def _apply_sqlite_migrations(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "tasks" in table_names:
        columns = {column["name"] for column in inspector.get_columns("tasks")}
        if "resolved_by_username" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE tasks ADD COLUMN resolved_by_username VARCHAR(64)")
                )
    if "staff_users" in table_names:
        staff_columns = {column["name"] for column in inspector.get_columns("staff_users")}
        alters: list[str] = []
        if "mfa_secret" not in staff_columns:
            alters.append("ALTER TABLE staff_users ADD COLUMN mfa_secret TEXT")
        if "mfa_enabled_at" not in staff_columns:
            alters.append(
                "ALTER TABLE staff_users ADD COLUMN mfa_enabled_at DATETIME"
            )
        if "mfa_last_step" not in staff_columns:
            alters.append("ALTER TABLE staff_users ADD COLUMN mfa_last_step INTEGER")
        if "email" not in staff_columns:
            alters.append("ALTER TABLE staff_users ADD COLUMN email VARCHAR(320)")
        if alters:
            with engine.begin() as connection:
                for statement in alters:
                    connection.execute(text(statement))
    if "tasks" in table_names:
        task_columns = {column["name"] for column in inspector.get_columns("tasks")}
        task_alters: list[str] = []
        if "inbound_message_id" not in task_columns:
            task_alters.append("ALTER TABLE tasks ADD COLUMN inbound_message_id INTEGER")
        if "inbound_subject" not in task_columns:
            task_alters.append("ALTER TABLE tasks ADD COLUMN inbound_subject VARCHAR(512)")
        if "reply_to_email" not in task_columns:
            task_alters.append("ALTER TABLE tasks ADD COLUMN reply_to_email VARCHAR(320)")
        if "reply_channel" not in task_columns:
            task_alters.append(
                "ALTER TABLE tasks ADD COLUMN reply_channel VARCHAR(32) DEFAULT 'email'"
            )
        if "reply_phone" not in task_columns:
            task_alters.append("ALTER TABLE tasks ADD COLUMN reply_phone VARCHAR(32)")
        if "booking_day" not in task_columns:
            task_alters.append("ALTER TABLE tasks ADD COLUMN booking_day VARCHAR(64)")
        if "booking_time" not in task_columns:
            task_alters.append("ALTER TABLE tasks ADD COLUMN booking_time VARCHAR(32)")
        if task_alters:
            with engine.begin() as connection:
                for statement in task_alters:
                    connection.execute(text(statement))
    if "inbound_messages" in table_names:
        inbound_columns = {
            column["name"] for column in inspector.get_columns("inbound_messages")
        }
        inbound_alters: list[str] = []
        if "source" not in inbound_columns:
            inbound_alters.append(
                "ALTER TABLE inbound_messages ADD COLUMN source VARCHAR(32) DEFAULT 'manual'"
            )
        if "external_id" not in inbound_columns:
            inbound_alters.append(
                "ALTER TABLE inbound_messages ADD COLUMN external_id VARCHAR(128)"
            )
        if "phone" not in inbound_columns:
            inbound_alters.append("ALTER TABLE inbound_messages ADD COLUMN phone VARCHAR(32)")
        if inbound_alters:
            with engine.begin() as connection:
                for statement in inbound_alters:
                    connection.execute(text(statement))
    if "outbox" in table_names:
        outbox_columns = {column["name"] for column in inspector.get_columns("outbox")}
        outbox_alters: list[str] = []
        if "to_email" not in outbox_columns:
            outbox_alters.append("ALTER TABLE outbox ADD COLUMN to_email VARCHAR(320)")
        if "delivered" not in outbox_columns:
            outbox_alters.append("ALTER TABLE outbox ADD COLUMN delivered BOOLEAN DEFAULT 0")
        if "delivery_error" not in outbox_columns:
            outbox_alters.append("ALTER TABLE outbox ADD COLUMN delivery_error VARCHAR(512)")
        if "channel" not in outbox_columns:
            outbox_alters.append(
                "ALTER TABLE outbox ADD COLUMN channel VARCHAR(32) DEFAULT 'email'"
            )
        if "to_phone" not in outbox_columns:
            outbox_alters.append("ALTER TABLE outbox ADD COLUMN to_phone VARCHAR(32)")
        if outbox_alters:
            with engine.begin() as connection:
                for statement in outbox_alters:
                    connection.execute(text(statement))


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
