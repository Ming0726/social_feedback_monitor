from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - used on clean Python envs
    yaml = None


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "keywords.yaml"


@dataclass(frozen=True)
class MonitorConfig:
    keywords: list[str]
    platforms: list[str]
    categories: dict[str, list[str]] = field(default_factory=dict)
    sentiment: dict[str, list[str]] = field(default_factory=dict)


def load_config(path: Path | str | None = None) -> MonitorConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG
    with config_path.open("r", encoding="utf-8") as f:
        if yaml:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        else:
            raw = _load_simple_yaml(f.read())

    return MonitorConfig(
        keywords=list(raw.get("keywords", [])),
        platforms=list(raw.get("platforms", [])),
        categories={k: list(v or []) for k, v in raw.get("categories", {}).items()},
        sentiment={k: list(v or []) for k, v in raw.get("sentiment", {}).items()},
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
            result[section] = [] if section in {"keywords", "platforms"} else {}
            continue
        if section in {"keywords", "platforms"} and stripped.startswith("- "):
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
