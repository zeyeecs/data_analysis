"""统一 color / condition 入库格式（F / R / V 三表共用）。"""

from __future__ import annotations

import ast
import unicodedata
from typing import Iterable

# 颜色：统一小写 ASCII 英文
_COLOR_ALIASES: dict[str, str] = {
    "noir": "black",
    "blanc": "white",
    "blanche": "white",
    "rouge": "red",
    "bleu": "blue",
    "bleue": "blue",
    "vert": "green",
    "verte": "green",
    "marron": "brown",
    "gris": "gray",
    "grise": "gray",
    "dore": "gold",
    "doré": "gold",
    "dorée": "gold",
    "argent": "silver",
    "argenté": "silver",
    "argentée": "silver",
    "rose": "pink",
    "jaune": "yellow",
    "violet": "purple",
    "violette": "purple",
    "orange": "orange",
    "beige": "beige",
    "multicolore": "multicolor",
    "multicolores": "multicolor",
    "black": "black",
    "blue": "blue",
    "blues": "blue",
    "brown": "brown",
    "browns": "brown",
    "gold": "gold",
    "gray": "gray",
    "grays": "gray",
    "grey": "gray",
    "greys": "gray",
    "green": "green",
    "greens": "green",
    "khaki": "khaki",
    "metallic": "metallic",
    "multicolor": "multicolor",
    "multicolour": "multicolor",
    "neutral": "neutral",
    "pink": "pink",
    "print": "print",
    "purple": "purple",
    "purples": "purple",
    "red": "red",
    "reds": "red",
    "silver": "silver",
    "white": "white",
    "whites": "white",
    "yellow": "yellow",
    "yellows": "yellow",
}

_COLOR_ORDER = (
    "beige",
    "black",
    "blue",
    "brown",
    "gold",
    "gray",
    "green",
    "khaki",
    "metallic",
    "multicolor",
    "neutral",
    "orange",
    "pink",
    "print",
    "purple",
    "red",
    "silver",
    "white",
    "yellow",
)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_condition(value: str | None) -> str | None:
    """保留飞书原始成色，仅做空值清理。"""
    return _clean_text(value)


def _parse_color_tokens(value: str) -> list[str]:
    text = value.strip()
    if not text or text == "[]":
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, str) and parsed.strip():
            return [parsed.strip()]

    if "/" in text:
        return [part.strip() for part in text.split("/") if part.strip()]

    return [text]


def _normalize_color_token(token: str) -> str | None:
    text = token.strip()
    if not text or text.lower() in {"color", "unknown", "n/a", "na", "none"}:
        return None

    lowered = text.lower()
    alias = _COLOR_ALIASES.get(lowered)
    if alias:
        return alias

    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(ch)
    )
    alias = _COLOR_ALIASES.get(folded)
    if alias:
        return alias

    if text.isupper() and len(text) <= 4:
        return lowered

    return folded if folded else lowered


def _sort_colors(colors: Iterable[str]) -> list[str]:
    order = {name: idx for idx, name in enumerate(_COLOR_ORDER)}

    def sort_key(name: str) -> tuple[int, str]:
        return (order.get(name, len(_COLOR_ORDER)), name)

    return sorted(set(colors), key=sort_key)


def normalize_color(value: str | None) -> str | None:
    """将各渠道原始颜色映射为小写 ASCII 英文；多色用 / 连接。"""
    text = _clean_text(value)
    if not text:
        return None

    normalized: list[str] = []
    for token in _parse_color_tokens(text):
        mapped = _normalize_color_token(token)
        if mapped:
            normalized.append(mapped)

    if not normalized:
        return None

    return "/".join(_sort_colors(normalized))
