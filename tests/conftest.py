from pathlib import Path

import pytest

from clerk.services.pages import PageStore
from clerk.services.policy import PolicyService

PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"


@pytest.fixture
def page_store() -> PageStore:
    return PageStore(PAGES_DIR)


@pytest.fixture
def policy(page_store: PageStore) -> PolicyService:
    return PolicyService(page_store)
