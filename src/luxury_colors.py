"""奢侈品专有色名词库（飞书「颜色」+ 竞品导出英文/法文色名）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_LEXICON_PATH = ROOT / "data" / "luxury_color_lexicon.txt"
_FEISHU_COLORS_PATH = ROOT / "data" / "feishu_colors_zh.txt"

# 内置高频词（文件未收录时仍生效）
_BUILTIN: tuple[str, ...] = (
    "Pivoine",
    "Peony",
    "Rose Ballerine",
    "Rose Gold",
    "Vert Fonce",
    "Rouge H",
    "Black Dune",
    "Mother of Pearl",
)


def _load_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        lines.append(text)
    return lines


@lru_cache(maxsize=1)
def luxury_color_lexicon() -> frozenset[str]:
    """小写形式词表，用于匹配。"""
    phrases: set[str] = set()
    for item in _BUILTIN:
        phrases.add(item.lower())
    for item in _load_lines(_LEXICON_PATH):
        phrases.add(item.lower())
    for item in _load_lines(_FEISHU_COLORS_PATH):
        phrases.add(item.lower())
    return frozenset(phrases)


@lru_cache(maxsize=1)
def luxury_color_phrases_sorted() -> tuple[str, ...]:
    """长词优先，供句中正则剥离（保留原文大小写）。"""
    phrases: list[str] = list(_BUILTIN)
    phrases.extend(_load_lines(_LEXICON_PATH))
    phrases.extend(_load_lines(_FEISHU_COLORS_PATH))
    unique = {p.lower(): p for p in phrases}
    return tuple(unique[k] for k in sorted(unique, key=len, reverse=True))
