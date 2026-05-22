from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


@dataclass
class FeedbackItem:
    item_type: str
    platform: str
    keyword: str
    text: str
    url: str
    published_at: str = ""
    author: str = ""
    likes_count: int | None = None
    comments_count: int | None = None
    parent_url: str = ""
    screenshot_path: str = ""
    sentiment: str = ""
    category: str = ""
    matched_keyword: str = ""
    feedback_category: str = ""
    mentioned_competitors: str = ""
    captured_at: str = ""

    def fingerprint(self) -> str:
        if self.item_type == "post" and self.url:
            basis = f"post|{self.platform}|{self.url}"
        else:
            basis = "|".join(
                [
                    self.item_type,
                    self.platform,
                    self.parent_url or self.url,
                    normalize_text(self.author),
                    normalize_text(self.published_at),
                    normalize_text(self.text),
                ]
            )
        return sha256(basis.encode("utf-8")).hexdigest()
