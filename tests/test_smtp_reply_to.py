from clerk.config import Settings
from clerk.services.smtp import build_outbound_message


def test_outbound_mail_replies_to_the_inbound_address() -> None:
    settings = Settings(
        smtp_from="Cape Town Physio <noreply@customchatandautomation.co.za>",
        clerk_inbound_address="clerk@customchatandautomation.co.za",
    )
    message = build_outbound_message(
        settings,
        to_address="patient@example.com",
        subject="Session fee",
        sender=settings.smtp_from,
        body="A standard session is R650.",
    )
    assert message["From"] == settings.smtp_from
    assert message["Reply-To"] == "clerk@customchatandautomation.co.za"


def test_outbound_mail_without_an_inbound_address_has_no_reply_to() -> None:
    settings = Settings(smtp_from="noreply@example.com", clerk_inbound_address="")
    message = build_outbound_message(
        settings,
        to_address="patient@example.com",
        subject="Hello",
        sender=settings.smtp_from,
        body="Hello",
    )
    assert message["Reply-To"] is None
