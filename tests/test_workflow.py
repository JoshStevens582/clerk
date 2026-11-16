import pytest

from clerk.repositories.db import create_db_engine, init_db, session_factory
from clerk.repositories.inbound_repo import InboundRepository
from clerk.repositories.models import TaskRow
from clerk.repositories.record_repo import RecordRepository
from clerk.schemas.agent import ClerkRunResult, PolicyOutcomeKind, ProposalKind
from clerk.schemas.channel import draft_kind_for_channel
from clerk.services.agent import ClerkAgentService
from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService
from clerk.services.workflow import ClerkWorkflow

PAGES = "pages"


@pytest.fixture
def workflow(tmp_path) -> ClerkWorkflow:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_db_engine(db_url)
    init_db(engine)
    factory = session_factory(engine)
    pages = PageStore(PAGES)
    settings = __import__("clerk.config", fromlist=["Settings"]).Settings(
        openai_api_key="",
        pages_dir=PAGES,
        database_url=db_url,
    )
    agent = ClerkAgentService(settings, pages)
    policy = PolicyService(pages)
    return ClerkWorkflow(agent, policy, factory)


@pytest.mark.asyncio
async def test_after_hours_auto_send(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Do you have anything on Thursday?",
        sample_id="after_hours_thursday",
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.auto_reply_text is not None


@pytest.mark.asyncio
async def test_booking_queues_without_slot(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Thursday 10:00",
        sample_id="booking_thursday_10",
    )
    assert result.outcome_kind == PolicyOutcomeKind.QUEUED
    assert result.queue_status == "pending"


@pytest.mark.asyncio
async def test_booking_updates_record_without_holding_slot(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Please book me for Thursday at 10:00.",
        sample_id="booking_thursday_10",
        reply_to_email="james@example.com",
        from_name="James Patel",
        channel="Web form",
    )
    assert result.record is not None
    assert result.record.display_name == "James Patel"
    assert result.record.booking_state == "prepared"
    assert result.record.booking_day == "Thursday"
    assert result.record.booking_time == "10:00"
    assert "not held" in result.record.note.lower()


class _EmptyDraftAgent:
    async def interpret(
        self,
        text: str,
        *,
        sample_id: str | None = None,
        channel: str | None = None,
    ) -> ClerkRunResult:
        del text, sample_id, channel
        return ClerkRunResult(kind=ProposalKind.WHATSAPP_DRAFT, draft_body="", cited_pages=[])


class _LimitSentenceAgent:
    async def interpret(
        self,
        text: str,
        *,
        sample_id: str | None = None,
        channel: str | None = None,
    ) -> ClerkRunResult:
        del text, sample_id, channel
        return ClerkRunResult(
            kind=ProposalKind.AUTO_REPLY,
            auto_reply_id="what_clerk_can_answer",
        )


@pytest.mark.asyncio
async def test_tuesday_at_10_waits_for_approval(workflow: ClerkWorkflow) -> None:
    repaired = ClerkWorkflow(workflow._agent, workflow._policy, workflow._db_factory)
    repaired._agent = _LimitSentenceAgent()  # type: ignore[assignment]
    result = await repaired.handle_message(
        "Can you please book me on Tuesday at 10",
        channel="WhatsApp",
        phone="+27820000000",
    )
    assert result.outcome_kind == PolicyOutcomeKind.QUEUED
    assert result.queue_status == "pending"
    assert result.auto_reply_text is None
    with repaired._db_factory() as session:
        task = session.get(TaskRow, result.task_id)
        assert task is not None
        assert task.kind == "booking_draft"
        assert task.status == "pending"
        assert task.booking_day == "Tuesday"
        assert task.booking_time == "10:00"
        assert task.reply_channel == "whatsapp"
        assert task.slot_held is False
        assert task.draft_body is not None
        assert "R650" in task.draft_body
        assert "Time not held until approved." in task.draft_body


@pytest.mark.asyncio
async def test_booking_on_a_day_without_a_time_sends_the_limit(
    workflow: ClerkWorkflow,
) -> None:
    repaired = ClerkWorkflow(workflow._agent, workflow._policy, workflow._db_factory)
    repaired._agent = _LimitSentenceAgent()  # type: ignore[assignment]
    result = await repaired.handle_message(
        "Can you please book me on Tuesday",
        channel="WhatsApp",
        phone="+27820000000",
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.queue_status == "sent_auto"


class _CitedBookingWithoutTime:
    async def interpret(
        self,
        text: str,
        *,
        sample_id: str | None = None,
        channel: str | None = None,
    ) -> ClerkRunResult:
        del text, sample_id, channel
        return ClerkRunResult(
            kind=ProposalKind.BOOKING_DRAFT,
            draft_body=(
                "A standard session is R650. We are open Monday to Friday. "
                "Reply with the day and time you want."
            ),
            cited_pages=["fees.md", "hours.md"],
            claimed_amounts=["R650"],
        )


@pytest.mark.asyncio
async def test_booking_without_a_time_sends_the_stored_limit(
    workflow: ClerkWorkflow,
) -> None:
    repaired = ClerkWorkflow(workflow._agent, workflow._policy, workflow._db_factory)
    repaired._agent = _CitedBookingWithoutTime()  # type: ignore[assignment]
    result = await repaired.handle_message(
        "I would like to book a session",
        reply_to_email="",
        channel="WhatsApp",
        phone="+27720510267",
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.auto_reply_text is not None
    assert "R650" not in result.auto_reply_text
    assert result.queue_status == "sent_auto"


@pytest.mark.asyncio
async def test_whatsapp_booking_without_a_draft_sends_the_stored_limit(
    workflow: ClerkWorkflow,
) -> None:
    repaired = ClerkWorkflow(workflow._agent, workflow._policy, workflow._db_factory)
    repaired._agent = _EmptyDraftAgent()  # type: ignore[assignment]
    with repaired._db_factory() as session:
        inbound = InboundRepository(session).create(
            from_name="Tester",
            from_email="",
            subject="WhatsApp message",
            body="I would like to book a session",
            channel="WhatsApp",
            phone="+27720510267",
            source="whatsapp",
        )
        session.commit()
        inbound_id = inbound.id

    result = await repaired.handle_message(
        "I would like to book a session",
        inbound_id=inbound_id,
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.auto_reply_text == (
        "Ask one of these and I will answer: What is the session fee? "
        "What are your opening hours? What do you treat? "
        "What documents do you need for a tax return? "
        "To book, tell me the day and the time, for example Tuesday at 10. "
        "A person replies to anything else."
    )
    with repaired._db_factory() as session:
        task = session.get(TaskRow, result.task_id)
        assert task is not None
        assert task.reply_channel == "whatsapp"
        assert task.reply_phone == "+27720510267"
        assert task.auto_reply_text == result.auto_reply_text
        assert task.slot_held is False


@pytest.mark.asyncio
async def test_available_times_sends_the_hours(workflow: ClerkWorkflow) -> None:
    repaired = ClerkWorkflow(workflow._agent, workflow._policy, workflow._db_factory)
    repaired._agent = _EmptyDraftAgent()  # type: ignore[assignment]
    result = await repaired.handle_message(
        "I want to book a session. what day and times are available?",
        reply_to_email="james@example.com",
        channel="Email",
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.queue_status == "sent_auto"
    assert result.auto_reply_text is not None
    assert "Monday to Friday" in result.auto_reply_text
    assert "close at 5:00 PM" in result.auto_reply_text
    assert "no list of open appointment times" in result.auto_reply_text
    assert "Ask one of these" not in result.auto_reply_text


@pytest.mark.asyncio
async def test_fee_and_hours_send_both_stored_sentences(workflow: ClerkWorkflow) -> None:
    repaired = ClerkWorkflow(workflow._agent, workflow._policy, workflow._db_factory)
    repaired._agent = _EmptyDraftAgent()  # type: ignore[assignment]
    result = await repaired.handle_message(
        "What is the session fee and what are your opening hours?",
        reply_to_email="james@example.com",
        channel="Email",
    )
    assert result.outcome_kind == PolicyOutcomeKind.SENT_AUTO
    assert result.auto_reply_text is not None
    assert "R650" in result.auto_reply_text
    assert "Monday to Friday" in result.auto_reply_text
    fee, hours = result.auto_reply_text.split("\n\n")
    assert fee.startswith("A standard one-on-one physiotherapy session is R650.")
    assert hours.startswith("We are open Monday to Friday")


@pytest.mark.asyncio
async def test_whatsapp_draft_updates_record_and_waits(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Please WhatsApp me the standard session fee.",
        sample_id="whatsapp_session_fee",
        reply_to_email="demo+thandi@customchatandautomation.co.za",
        from_name="Thandi Jacobs",
        channel="WhatsApp",
        phone="+27820000000",
    )
    assert result.outcome_kind == PolicyOutcomeKind.QUEUED
    assert result.record is not None
    assert result.record.last_channel == "WhatsApp"
    assert result.record.phone == "+27820000000"
    assert result.record.booking_state == "none"
    assert "not sent" in result.record.note.lower()
    assert "waiting for approval" in result.record.note.lower()


@pytest.mark.asyncio
async def test_email_sample_on_whatsapp_is_drafted_as_whatsapp(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Email me what you need for the tax return.",
        sample_id="tax_return_email",
        reply_to_email="thandi@example.com",
        channel="WhatsApp",
    )
    assert result.record is not None
    assert "WhatsApp draft" in result.record.note
    with workflow._db_factory() as session:
        task = session.get(TaskRow, result.task_id)
        assert task is not None
        assert task.kind == "whatsapp_draft"
        assert task.reply_channel == "whatsapp"


@pytest.mark.asyncio
async def test_missing_inbound_is_rejected(workflow: ClerkWorkflow) -> None:
    with pytest.raises(ValueError, match="not found"):
        await workflow.handle_message("Hello", inbound_id=999)


@pytest.mark.asyncio
async def test_inbound_is_handled_once(workflow: ClerkWorkflow) -> None:
    with workflow._db_factory() as session:
        inbound = InboundRepository(session).create(
            from_name="Sarah Nkomo",
            from_email="demo+sarah@customchatandautomation.co.za",
            subject="Anything on Thursday?",
            body="Do you have anything on Thursday?",
            channel="Email",
            sample_id="after_hours_thursday",
        )
        session.commit()
        inbound_id = inbound.id

    first = await workflow.handle_message(
        "Do you have anything on Thursday?",
        inbound_id=inbound_id,
        inbound_subject="Kept subject",
    )
    assert first.record is not None
    assert first.record.note.startswith("Agreed reply sent")
    with workflow._db_factory() as session:
        task = session.get(TaskRow, first.task_id)
        assert task is not None
        assert task.inbound_subject == "Kept subject"
    with pytest.raises(ValueError, match="already handled"):
        await workflow.handle_message(
            "Do you have anything on Thursday?",
            inbound_id=inbound_id,
        )


@pytest.mark.asyncio
async def test_message_without_email_does_not_write_a_record(workflow: ClerkWorkflow) -> None:
    result = await workflow.handle_message(
        "Email me what you need for the tax return.",
        sample_id="tax_return_email",
    )
    assert result.record is None


@pytest.mark.asyncio
async def test_later_update_keeps_name_and_phone(workflow: ClerkWorkflow) -> None:
    first = await workflow.handle_message(
        "Please WhatsApp me the standard session fee.",
        sample_id="whatsapp_session_fee",
        reply_to_email="thandi@example.com",
        from_name="Thandi Jacobs",
        channel="WhatsApp",
        phone="+27820000000",
    )
    assert first.record is not None
    second = await workflow.handle_message(
        "Email me what you need for the tax return.",
        sample_id="tax_return_email",
        reply_to_email="thandi@example.com",
        from_name=" ",
        channel="Email",
    )
    assert second.record is not None
    assert second.record.display_name == "Thandi Jacobs"
    assert second.record.phone == "+27820000000"
    assert second.record.booking_state == "none"
    assert second.record.note.startswith("Email draft")


def test_blank_demo_addresses_still_clear_demo_plus_records(workflow: ClerkWorkflow) -> None:
    with workflow._db_factory() as session:
        RecordRepository(session).upsert(
            email="demo+keep@customchatandautomation.co.za",
            display_name="Demo",
            phone=None,
            last_channel="Email",
            last_request="Hello",
            note="Sample",
        )
        RecordRepository(session).upsert(
            email="live@example.com",
            display_name="Live",
            phone=None,
            last_channel="Email",
            last_request="Hello",
            note="Live",
        )
        RecordRepository(session).delete_demo_contacts({""})
        session.commit()
        repo = RecordRepository(session)
        assert repo.get_by_email("demo+keep@customchatandautomation.co.za") is None
        assert repo.get_by_email("live@example.com") is not None
        assert repo.get_by_email("   ") is None


def test_decision_without_inbound_or_email(workflow: ClerkWorkflow) -> None:
    from clerk.services.records import apply_task_decision

    with workflow._db_factory() as session:
        task = TaskRow(
            status="pending",
            kind="email_draft",
            inbound_text="Please email the tax list.",
            reply_to_email=None,
            reply_channel="email",
            outcome_message="",
            cited_pages_json="[]",
        )
        session.add(task)
        session.flush()
        assert apply_task_decision(session, task, approved=True) is None
        task.reply_to_email = "solo@example.com"
        task.inbound_message_id = 999
        updated = apply_task_decision(session, task, approved=True)
        assert updated is not None
        assert updated.email == "solo@example.com"
        assert updated.note.startswith("Email approved")
        assert updated.display_name == "solo"


def test_email_draft_on_whatsapp_channel_changes_kind() -> None:
    email_on_whatsapp = draft_kind_for_channel(ProposalKind.EMAIL_DRAFT, "WhatsApp")
    whatsapp_on_email = draft_kind_for_channel(ProposalKind.WHATSAPP_DRAFT, "Email")
    booking_on_whatsapp = draft_kind_for_channel(ProposalKind.BOOKING_DRAFT, "WhatsApp")
    assert email_on_whatsapp == ProposalKind.WHATSAPP_DRAFT
    assert whatsapp_on_email == ProposalKind.EMAIL_DRAFT
    assert booking_on_whatsapp == ProposalKind.BOOKING_DRAFT
