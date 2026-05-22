from __future__ import annotations

import csv
from pathlib import Path

from .analyzer import analyze_item
from .config import MonitorConfig
from .keyword_filter import match_keywords
from .models import FeedbackItem


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def import_csv(path: Path | str, config: MonitorConfig) -> list[FeedbackItem]:
    items: list[FeedbackItem] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            item = FeedbackItem(
                item_type=str(row.get("item_type", "post")).strip() or "post",
                platform=str(row.get("platform", "")).strip(),
                keyword=str(row.get("keyword", "")).strip(),
                text=str(row.get("text", "")).strip(),
                url=str(row.get("url", "")).strip(),
                published_at=str(row.get("published_at", "")).strip(),
                author=str(row.get("author", "")).strip(),
                likes_count=_optional_int(row.get("likes_count")),
                comments_count=_optional_int(row.get("comments_count")),
                parent_url=str(row.get("parent_url", "")).strip(),
                screenshot_path=str(row.get("screenshot_path", "")).strip(),
            )
            if item.platform and item.text and match_keywords(item.text, config):
                items.append(analyze_item(item, config))
    return items
