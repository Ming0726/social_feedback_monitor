from __future__ import annotations

from dataclasses import dataclass

from .config import MonitorConfig


@dataclass(frozen=True)
class KeywordMatch:
    matched_keyword: str
    feedback_category: str
    mentioned_competitors: str = ""


def match_keywords(text: str, config: MonitorConfig, context_text: str = "") -> KeywordMatch | None:
    candidate = f"{context_text}\n{text}".strip()
    if len(candidate.strip()) < config.min_text_length:
        return None

    matched_strong = _matched_words(candidate, config.strong_keywords)
    matched_weak = _matched_words(candidate, config.weak_keywords)
    matched_all = matched_strong + matched_weak
    mentioned_competitors = _matched_words(
        candidate,
        config.competitors_direct + config.competitors_other,
    )
    has_context = bool(_matched_words(candidate, config.context_words))
    has_red_packet = "红包" in candidate

    if not matched_all and not (has_context and mentioned_competitors and has_red_packet):
        return None

    if not matched_all and has_context and mentioned_competitors and has_red_packet:
        matched_all = ["红包"]

    if config.spam_keywords and _matched_words(candidate, config.spam_keywords):
        return None

    if matched_all and all(keyword in config.exclude_keywords_if_only for keyword in matched_all):
        return None

    if mentioned_competitors:
        matched_menu_words = _matched_words(candidate, config.menu_weak_keywords)
        if not has_context and not matched_menu_words:
            return None
        return KeywordMatch(
            matched_keyword="|".join(matched_all),
            feedback_category="competitor_compare",
            mentioned_competitors="|".join(mentioned_competitors),
        )

    if matched_weak and not matched_strong and not has_context:
        return None

    return KeywordMatch(
        matched_keyword="|".join(matched_all),
        feedback_category="feedback",
    )


def _matched_words(text: str, words: list[str]) -> list[str]:
    matched: list[str] = []
    lower_text = text.lower()
    for word in words:
        if not word:
            continue
        if _contains_word(lower_text, word):
            matched.append(word)
    return _dedupe(matched)


def _contains_word(lower_text: str, word: str) -> bool:
    if any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in word):
        return word.lower() in lower_text
    return word in lower_text


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
