"""Demo inbox rows for new databases (matches the original desk samples)."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from clerk.repositories.inbound_repo import InboundRepository

DEMO_INBOX: list[dict[str, str | None]] = [
    {
        "from_name": "Sarah Nkomo",
        "from_email": "demo+sarah@customchatandautomation.co.za",
        "subject": "Anything on Thursday?",
        "body": "Do you have anything on Thursday?",
        "channel": "Email",
        "sample_id": "after_hours_thursday",
    },
    {
        "from_name": "James Patel",
        "from_email": "demo+james@customchatandautomation.co.za",
        "subject": "Booking request — Thursday morning",
        "body": "Please book me for Thursday at 10:00.",
        "channel": "Web form",
        "sample_id": "booking_thursday_10",
    },
    {
        "from_name": "Lindiwe Mokoena",
        "from_email": "demo+lindiwe@customchatandautomation.co.za",
        "subject": "Tax return — what to send",
        "body": "Email me what you need for the tax return.",
        "channel": "Email",
        "sample_id": "tax_return_email",
    },
    {
        "from_name": "Internal — front desk",
        "from_email": "demo+frontdesk@customchatandautomation.co.za",
        "subject": "Leave carry-over — action needed",
        "body": "Email HR that I want those 5 days carry-over leave.",
        "channel": "Email",
        "sample_id": "leave_hr_email",
    },
]


def seed_demo_inbox(db_factory: sessionmaker[Session]) -> None:
    with db_factory() as session:
        repo = InboundRepository(session)
        if repo.count() > 0:
            return
        for item in DEMO_INBOX:
            repo.create(
                from_name=str(item["from_name"]),
                from_email=str(item["from_email"]),
                subject=str(item["subject"]),
                body=str(item["body"]),
                channel=str(item["channel"]),
                sample_id=item["sample_id"],
            )
        session.commit()
