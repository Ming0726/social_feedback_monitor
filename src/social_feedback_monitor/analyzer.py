from __future__ import annotations

from .config import MonitorConfig
from .models import FeedbackItem


def contains_any(text: str, words: list[str]) -> bool:
    return any(word and word in text for word in words)


def analyze_item(item: FeedbackItem, config: MonitorConfig) -> FeedbackItem:
    text = item.text or ""

    positive = contains_any(text, config.sentiment.get("positive", []))
    negative = contains_any(text, config.sentiment.get("negative", []))
    if negative and not positive:
        item.sentiment = "负向"
    elif positive and not negative:
        item.sentiment = "正向"
    elif positive and negative:
        item.sentiment = "混合"
    else:
        item.sentiment = "中性"

    item.category = "其他"
    for category, words in config.categories.items():
        if contains_any(text, words):
            item.category = category
            break

    if not item.keyword:
        for keyword in config.keywords:
            if keyword in text:
                item.keyword = keyword
                break

    return item
