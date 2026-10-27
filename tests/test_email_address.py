from clerk.services.email_address import split_from_address


def test_split_from_with_display_name() -> None:
    name, email = split_from_address("Jane Doe <jane@example.com>")
    assert name == "Jane Doe"
    assert email == "jane@example.com"


def test_split_from_bare_email() -> None:
    name, email = split_from_address("jane@example.com")
    assert name == "jane@example.com"
    assert email == "jane@example.com"
