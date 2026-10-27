"""Parse From headers into display name + address."""

from __future__ import annotations

import re

_FROM_WITH_NAME = re.compile(r"^\s*(?P<name>.+?)\s*<(?P<email>[^>]+)>\s*$")
_FROM_EMAIL_ONLY = re.compile(r"^\s*(?P<email>[^\s<>]+@[^\s<>]+)\s*$")


def split_from_address(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if not text:
        return ("Unknown sender", "")
    match = _FROM_WITH_NAME.match(text)
    if match:
        name = match.group("name").strip().strip('"')
        email = match.group("email").strip().lower()
        return (name or email, email)
    match = _FROM_EMAIL_ONLY.match(text)
    if match:
        email = match.group("email").strip().lower()
        return (email, email)
    return (text, text.lower() if "@" in text else "")
