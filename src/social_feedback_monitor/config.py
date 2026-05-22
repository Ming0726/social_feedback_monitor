from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - used on clean Python envs
    yaml = None


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "keywords.yaml"

STRONG_KEYWORDS = [
    "微信面对面红包",
    "微信 面对面红包",
    "微信扫码红包",
    "微信 扫码红包",
    "微信二维码红包",
    "面对面红包打不开",
    "面对面红包扫不出",
    "面对面红包扫不了",
    "面对面红包用不了",
]

WEAK_KEYWORDS = [
    "面对面红包",
    "扫码红包",
    "面对面发红包",
    "面对面收红包",
]

CONTEXT_WORDS = ["微信", "WeChat", "wechat", "wx", "WX"]

COMPETITORS_DIRECT = [
    "支付宝",
    "云闪付",
    "数字人民币",
    "招商银行",
    "招行",
    "QQ红包",
    "qq红包",
    "翼支付",
    "京东支付",
    "京东钱包",
]

COMPETITORS_OTHER = [
    "抖音红包",
    "抖音活动",
    "快手红包",
    "拼多多",
    "美团红包",
    "滴滴红包",
    "饿了么红包",
    "京东红包",
    "百度红包",
    "淘宝",
    "天猫",
]

EXCLUDE_KEYWORDS_IF_ONLY = [
    "群红包",
    "拼手气红包",
    "口令红包",
    "封面红包",
]

MENU_WEAK_KEYWORDS = [
    "面对面发红包",
    "面对面收红包",
]


@dataclass(frozen=True)
class MonitorConfig:
    keywords: list[str]
    platforms: list[str]
    categories: dict[str, list[str]] = field(default_factory=dict)
    sentiment: dict[str, list[str]] = field(default_factory=dict)
    strong_keywords: list[str] = field(default_factory=lambda: list(STRONG_KEYWORDS))
    weak_keywords: list[str] = field(default_factory=lambda: list(WEAK_KEYWORDS))
    context_words: list[str] = field(default_factory=lambda: list(CONTEXT_WORDS))
    competitors_direct: list[str] = field(default_factory=lambda: list(COMPETITORS_DIRECT))
    competitors_other: list[str] = field(default_factory=lambda: list(COMPETITORS_OTHER))
    exclude_keywords_if_only: list[str] = field(default_factory=lambda: list(EXCLUDE_KEYWORDS_IF_ONLY))
    menu_weak_keywords: list[str] = field(default_factory=lambda: list(MENU_WEAK_KEYWORDS))
    spam_keywords: list[str] = field(default_factory=list)
    min_text_length: int = 8


def load_config(path: Path | str | None = None) -> MonitorConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG
    with config_path.open("r", encoding="utf-8") as f:
        if yaml:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        else:
            raw = _load_simple_yaml(f.read())

    strong_keywords = list(raw.get("strong_keywords", STRONG_KEYWORDS))
    weak_keywords = list(raw.get("weak_keywords", WEAK_KEYWORDS))
    keywords = list(raw.get("keywords") or strong_keywords + weak_keywords)

    return MonitorConfig(
        keywords=keywords,
        platforms=list(raw.get("platforms", [])),
        categories={k: list(v or []) for k, v in raw.get("categories", {}).items()},
        sentiment={k: list(v or []) for k, v in raw.get("sentiment", {}).items()},
        strong_keywords=strong_keywords,
        weak_keywords=weak_keywords,
        context_words=list(raw.get("context_words", CONTEXT_WORDS)),
        competitors_direct=list(raw.get("competitors_direct", COMPETITORS_DIRECT)),
        competitors_other=list(raw.get("competitors_other", COMPETITORS_OTHER)),
        exclude_keywords_if_only=list(raw.get("exclude_keywords_if_only", EXCLUDE_KEYWORDS_IF_ONLY)),
        menu_weak_keywords=list(raw.get("menu_weak_keywords", MENU_WEAK_KEYWORDS)),
        spam_keywords=list(raw.get("spam_keywords", [])),
        min_text_length=int(raw.get("min_text_length", 8)),
    )


def _load_simple_yaml(text: str) -> dict[str, Any]:
    """Tiny parser for this tool's default config when PyYAML is unavailable."""
    result: dict[str, Any] = {}
    section: str | None = None
    subsection: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            subsection = None
            result[section] = [] if section not in {"categories", "sentiment"} else {}
            continue
        if section and isinstance(result.get(section), list) and stripped.startswith("- "):
            result[section].append(stripped[2:].strip())
            continue
        if section in {"categories", "sentiment"}:
            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
                subsection = stripped[:-1]
                result[section][subsection] = []
                continue
            if subsection and stripped.startswith("- "):
                result[section][subsection].append(stripped[2:].strip())

    return result
