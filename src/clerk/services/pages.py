import json
from pathlib import Path

from pydantic import BaseModel, Field


class ApprovedReply(BaseModel):
    id: str
    text: str


class ApprovedReplyCatalog(BaseModel):
    replies: list[ApprovedReply] = Field(default_factory=list)

    def by_id(self, reply_id: str) -> ApprovedReply | None:
        for reply in self.replies:
            if reply.id == reply_id:
                return reply
        return None


class PageStore:
    def __init__(self, pages_dir: str | Path) -> None:
        self._root = Path(pages_dir)

    @property
    def root(self) -> Path:
        return self._root

    def read_page(self, name: str) -> str:
        normalized = name.strip()
        if not normalized.endswith(".md"):
            normalized = f"{normalized}.md"
        path = self._root / normalized
        if not path.is_file():
            msg = f"Page not found: {name}"
            raise FileNotFoundError(msg)
        return path.read_text(encoding="utf-8")

    def load_approved_replies(self) -> ApprovedReplyCatalog:
        path = self._root / "approved-replies.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ApprovedReplyCatalog.model_validate(raw)

    def list_markdown_pages(self) -> list[str]:
        return sorted(p.name for p in self._root.glob("*.md"))
