"""商品名称/型号/材质/颜色的英文归一化（法文等多语言 → 小写 ASCII 英文）。"""

from __future__ import annotations

import re
import unicodedata

# 多词法文包型/描述（长词优先）→ 小写英文
_NAME_PHRASE_EN: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(pattern, re.IGNORECASE),
        replacement,
    )
    for pattern, replacement in (
        (r"\bsac\s+ceinture\b", "belt bag"),
        (r"\bsac\s+[àa]\s+main\b", "handbag"),
        (r"\bporte[\s-]?monnaie\b", "wallet"),
        (r"\bportefeuille\b", "wallet"),
        (r"\bsac\s+[àa]\s+dos\b", "backpack"),
        (r"\bpetit\s+sac\b", "small bag"),
        (r"\bgrand\s+sac\b", "large bag"),
        (r"\bmulti\s+pochette\s+accessoires\b", "multi pochette accessories"),
    )
)

_NAME_WORD_EN: dict[str, str] = {
    "accessoires": "accessories",
    "bandoulière": "bandouliere",
    "bandouliere": "bandouliere",
    "ceinture": "belt",
    "trousse": "pouch",
    "toile": "canvas",
    "cuir": "leather",
    "soie": "silk",
    "laine": "wool",
    "velours": "velvet",
}

_MATERIAL_PHRASE_EN: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(pattern, re.IGNORECASE),
        replacement,
    )
    for pattern, replacement in (
        (r"\bpeau\s+de\s+veau\b", "calfskin"),
        (r"\bvegan\s+cuir\b", "vegan leather"),
        (r"\bcuir\s+vegan\b", "vegan leather"),
        (r"\btoile\s+et\s+cuir\b", "canvas and leather"),
        (r"\btoile\s+and\s+leather\b", "canvas and leather"),
    )
)

_BRAND_CANONICAL: dict[str, str] = {
    "hermes": "hermes",
    "hermès": "hermes",
    "chloe": "chloe",
    "chloé": "chloe",
    "celine": "celine",
    "céline": "celine",
    "alaia": "alaia",
    "alaïa": "alaia",
    "yvessaintlaurent": "yves saint laurent",
    "tiffany&co.": "tiffany & co.",
    "tiffany&co": "tiffany & co.",
}

_BRAND_PHRASE_EN: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(pattern, re.IGNORECASE),
        replacement,
    )
    for pattern, replacement in (
        (r"\bnon\s+sign[ée]\b", "non signed"),
        (r"\bsee\s+by\s+chlo[ée]\b", "see by chloe"),
    )
)

_MATERIAL_WORD_EN: dict[str, str] = {
    "cuir": "leather",
    "toile": "canvas",
    "soie": "silk",
    "laine": "wool",
    "velours": "velvet",
    "serpent": "snake",
    "autruche": "ostrich",
    "crocodile": "crocodile",
    "alligator": "alligator",
    "daim": "suede",
    "coton": "cotton",
    "denim": "denim",
    "paille": "straw",
    "osier": "wicker",
}


def _fold_accents(text: str) -> str:
    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )
    return folded.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")


def finalize_english_lower(value: str | None) -> str | None:
    """统一为小写 ASCII 英文；含中文则原样保留。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.search(r"[\u4e00-\u9fff]", text):
        return text
    return _fold_accents(text).lower()


def _apply_phrase_map(text: str, rules: tuple[tuple[re.Pattern[str], str], ...]) -> str:
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text


def _apply_word_map(text: str, word_map: dict[str, str]) -> str:
    tokens = text.split()
    if not tokens:
        return text
    out: list[str] = []
    for token in tokens:
        m = re.match(r"^([^A-Za-z0-9]*)([A-Za-z0-9À-ÿ][A-Za-z0-9À-ÿ'.-]*)([^A-Za-z0-9À-ÿ]*)$", token)
        if not m:
            out.append(_fold_accents(token))
            continue
        lead, core, trail = m.group(1), m.group(2), m.group(3)
        mapped = word_map.get(core.lower())
        core = mapped if mapped else _fold_accents(core)
        out.append(f"{lead}{core}{trail}")
    return " ".join(out)


def normalize_brand_english(value: str | None) -> str | None:
    """品牌：法文/重音 → 小写 ASCII 英文。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    text = _apply_phrase_map(text, _BRAND_PHRASE_EN)
    folded_key = _fold_accents(text).lower()
    if folded_key in _BRAND_CANONICAL:
        return _BRAND_CANONICAL[folded_key]

    if "/" in text:
        parts = [normalize_brand_english(part.strip()) or part.strip() for part in text.split("/")]
        return " / ".join(parts)

    return finalize_english_lower(text)


def normalize_name_english(value: str | None) -> str | None:
    """型号/商品名：法文词与重音 → 小写 ASCII 英文。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.search(r"[\u4e00-\u9fff]", text):
        return text

    text = _apply_phrase_map(text, _NAME_PHRASE_EN)
    text = _apply_word_map(text, _NAME_WORD_EN)
    text = re.sub(r"\s+", " ", text).strip()
    return finalize_english_lower(text)


def normalize_material_english(value: str | None) -> str | None:
    """材质列：法文 → 小写 ASCII 英文。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    text = _apply_phrase_map(text, _MATERIAL_PHRASE_EN)
    tokens = re.split(r"(\s+)", text)
    mapped_tokens: list[str] = []
    for token in tokens:
        if not token.strip():
            mapped_tokens.append(token)
            continue
        core_match = re.match(r"^([^A-Za-z0-9À-ÿ]*)([A-Za-z0-9À-ÿ][A-Za-z0-9À-ÿ'.-]*)(.*)$", token)
        if not core_match:
            mapped_tokens.append(_fold_accents(token))
            continue
        lead, core, trail = core_match.groups()
        replacement = _MATERIAL_WORD_EN.get(core.lower())
        core = replacement if replacement else _fold_accents(core)
        mapped_tokens.append(f"{lead}{core}{trail}")
    text = "".join(mapped_tokens)
    text = re.sub(r"\s+", " ", text).strip()
    return finalize_english_lower(text)
