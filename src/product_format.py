"""将 F / R / V 竞品行格式化为统一商品字段（参考飞书采购表结构，不含业务扩展列）。"""

from __future__ import annotations

import ast
import re
from difflib import SequenceMatcher
from typing import Any

from src.field_normalize import _COLOR_ALIASES, normalize_color
from src.name_normalize import (
    _fold_accents,
    normalize_brand_english,
    normalize_material_english,
    normalize_name_english,
)
from src.luxury_colors import luxury_color_lexicon, luxury_color_phrases_sorted

_FUZZY_THRESHOLD = 0.86

# 成色 → 成色判断（中文档位/英文原值），与飞书采购表一致
_CONDITION_GRADES: dict[str, tuple[str, str]] = {
    "new": ("全新", "New"),
    "giftable": ("全新", "Giftable"),
    "never worn": ("全新", "Never worn"),
    "never worn, with tag": ("全新", "Never worn, with tag"),
    "excellent": ("99新", "Excellent"),
    "great": ("98新", "Great"),
    "very good": ("97新", "Very Good"),
    "good": ("95新", "Good"),
    "shows wear": ("90新", "Shows Wear"),
    "worn": ("85新", "Worn"),
    "fair": ("85新", "Fair"),
    "very good condition": ("97新", "Very good condition"),
    "good condition": ("95新", "Good condition"),
    "fair condition": ("85新", "Fair condition"),
}

# 材质词表（长词优先）；正则按词边界匹配，支持前缀/嵌入/后缀
_MATERIAL_PATTERNS: tuple[str, ...] = (
    "Monogram Multicolor",
    "Monogram Eclipse Canvas",
    "Monogram Canvas",
    "GG Coated Canvas and Leather",
    "GG Coated Canvas",
    "Microguccissima Leather",
    "Quilted Patent",
    "GG Canvas",
    "Damier Azur",
    "Damier Ebene",
    "Damier Graphite",
    "Coated Canvas",
    "Patent Leather",
    "Plated Metal and Leather",
    "Monogram",
    "Damier",
    "Empreinte",
    "Multicolor",
    "Vernis",
    "Taiga",
    "Shearling",
    "Macassar",
    "Epi",
    "Toile and Leather",
    "Toile",
    "Canvas",
    "Patent",
    "Leather",
    "Suede",
    "Calfskin",
    "Raffia",
    "Wicker",
    "Epsom",
    "Togo",
    "Swift",
    "Clemence",
    "Chevre",
    "Box Calf",
    "Barenia",
    "Taurillon",
    "Vache",
    "Chevre",
    "Clemence",
    "Mysore",
    "Ostrich",
    "Alligator",
    "Crocodile",
    "Lizard",
    "Fjord",
    "Evercolor",
    "Novillo",
    "Gulliver",
    "Doblis",
    "Negonda",
    "TC",
)

_V_SUFFIX_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        rf"\s+{re.escape(suffix.lstrip())}\s*$",
        re.IGNORECASE,
    )
    for suffix in (
        "leather crossbody bag",
        "leather handbag",
        "cloth crossbody bag",
        "cloth handbag",
        "cotton crossbody bag",
        "wicker crossbody bag",
        "crossbody bag",
        "shoulder bag",
        "handbag",
        "tote bag",
        "belt bag",
        "clutch",
        "wallet",
        "watch",
    )
)

# 爱马仕刻印年份（飞书「年份」列）；勿将型号末尾数字（如墨镜 6059、1955 款）误判为年份
_HERMES_YEAR_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|\s)(框\s?[A-Z](?:/\d{4})?)(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|\s)([A-Z]/\d{4})(?:\s|$)"),
)

# 包型/品类词（从型号中剔除，飞书「型号」仅保留款式+尺码）
_BAG_TYPE_PHRASES: tuple[str, ...] = (
    "Adjustable Shoulder Strap",
    "Convertible Open",
    "Crossbody Bag",
    "Shoulder Bag",
    "Messenger Bag",
    "Bucket Bag",
    "Bowling Bag",
    "Satchel",
    "Backpack",
    "Handbag",
    "Wristlet",
    "Clutch",
    "Hobo",
    "Tote",
    "Belt Bag",
    "Bag",
)

# 修饰词（非款式名）；长词优先，句中任意位置剔除
_MODEL_MODIFIER_PHRASES: tuple[str, ...] = (
    "with Permabrass Hardware",
    "with Palladium Hardware",
    "with Rose Gold Hardware",
    "with Gold Hardware",
    "with Silver Hardware",
    "with Brushed Hardware",
    "with Hardware",
    "Permabrass Hardware",
    "Palladium Hardware",
    "Rose Gold Hardware",
    "Gold Hardware",
    "Silver Hardware",
    "Hardware",
    "Embellished",
    "Convertible",
    "Adjustable",
    "Woven",
    "Open",
    "Coated Canvas",
    "Print",
    "Vintage",
    "Quilted",
)

_SIZE_TOKEN_RE = re.compile(
    r"^(?:bb|pm|mm|gm|nm|tp|nano|mini|small|medium|large|micro|xs|xl|long|wide|\d{1,2})$",
    re.IGNORECASE,
)

_ALPHA_NUM_MODEL_RE = re.compile(r"^([A-Za-z][A-Za-z.\-]*?)(\d{1,2})$")

# 爱马仕等款式的工艺/结构变体（非款式名、非尺码）；仅紧跟款式线时剥离至 other 列
_HERMES_LINE_NAMES = frozenset(
    {
        "kelly",
        "birkin",
        "constance",
        "bolide",
        "lindy",
        "picotin",
        "evelyne",
        "herbag",
        "halzan",
        "roulis",
        "verrou",
        "toolbox",
        "jypsiere",
        "jige",
        "drag",
        "geta",
        "cabana",
        "in-the-loop",
        "24/24",
        "videpoches",
    }
)
_MODEL_OTHER_TOKENS = frozenset({"sellier", "retourne", "touch", "cargo", "faubourg"})
_MODEL_OTHER_PHRASES = frozenset({"so black"})
_VALID_OTHER_PARTS = _MODEL_OTHER_TOKENS | _MODEL_OTHER_PHRASES

# LLM 误拆时合并回 model：(other 词/短语, model 需含的关键词, 合并位置, 可选固定补全后缀)
_MODEL_OTHER_REJOIN: tuple[tuple[str, frozenset[str], str, str | None], ...] = (
    ("gg", frozenset({"marmont", "supreme", "sylvie", "ophidia", "padlock", "horsebit", "blondie", "bamboo"}), "prefix", None),
    ("bandouliere", frozenset({"speedy", "neverfull", "alma", "deauville", "keepall"}), "suffix", None),
    ("rockstud", frozenset({"spike", "glam", "lock", "stud"}), "prefix", None),
    ("tassel", frozenset({"oval"}), "prefix", None),
    ("top handle", frozenset({"cc", "bamboo", "daily", "boy", "classic", "kelly", "birkin"}), "suffix", None),
    ("top", frozenset({"cc", "bamboo"}), "suffix", "top handle"),
    ("east west", frozenset({"click"}), "suffix", None),
    ("noeud", frozenset({"chiquito"}), "suffix", None),
    ("box", frozenset({"falabella"}), "suffix", None),
    ("re-edition", frozenset({"2005", "2000", "2002", "1995", "1994"}), "prefix", None),
    ("zip", frozenset({"herbag"}), "suffix", None),
    ("fold", frozenset({"puzzle"}), "suffix", None),
    ("cargo", frozenset({"ramones"}), "prefix", None),
    ("cargo", frozenset({"jonathan", "field", "carryall", "boston", "duffle", "hobo"}), "suffix", None),
)

# 成色词（从型号任意位置剔除；不含 new，避免误伤 New Wave 等款式名）
_CONDITION_STRIP_PHRASES: tuple[str, ...] = (
    "never worn, with tag",
    "never worn with tag",
    "very good condition",
    "good condition",
    "fair condition",
    "shows wear",
    "never worn",
    "very good",
    "excellent",
    "giftable",
    "great",
    "fair",
    "worn",
)

_CONDITION_EDGE_RE = re.compile(
    r"^(?:Excellent|Great|Giftable|Fair|Worn)\s+|\s+(?:Excellent|Great|Giftable|Fair|Worn)\s*$",
    re.IGNORECASE,
)

# 词库色名可能是款式名一部分（如 Kelly Quartz Watch），勿当颜色剔除
_COLOR_STRIP_GUARD_RE = re.compile(
    r"\b(?:quartz|ceramic|steel)\s+watch\b",
    re.IGNORECASE,
)

# 常见多词颜色（长词优先；与 field_normalize 基础色合并）
_COLOR_EXTRA_PHRASES: tuple[str, ...] = (
    "Mother of Pearl",
    "Mother-of-Pearl",
    "Rose Ballerine",
    "Rose Gold",
    "White Gold",
    "Yellow Gold",
    "Rose Shocking",
    "Rose Azalee",
    "Rose Jaipur",
    "Vert Fonce",
    "Rouge H",
    "Black Dune",
    "Stainless Steel",
    "Rose Gold",
    "Gunmetal",
    "Champagne",
    "Porcelain",
    "Multicolour",
)


def _color_strip_phrases() -> tuple[str, ...]:
    singles = {name for name in _COLOR_ALIASES.values()}
    singles.update(k.title() for k in _COLOR_ALIASES)
    singles.update(
        {
            "Noir",
            "Rouge",
            "Vert",
            "Bleu",
            "Dune",
            "Alezan",
            "Ivory",
            "Cream",
            "Tan",
            "Navy",
            "Burgundy",
            "Coral",
            "Fonce",
            "Azalee",
            "Jaipur",
            "Shocking",
            "Ballerine",
        }
    )
    merged = set(_COLOR_EXTRA_PHRASES) | singles
    merged.update(luxury_color_phrases_sorted())
    return tuple(sorted(merged, key=len, reverse=True))


def _strip_trailing_lexicon_colors(text: str, found: list[str]) -> str:
    """从尾部剥离词库中的专有色名（如 Pivoine），遇到尺码 token 则停止。"""
    tokens = text.split()
    if not tokens:
        return text
    lex = luxury_color_lexicon()
    while len(tokens) > 1:
        if _is_size_token(tokens[-1]):
            break
        removed: str | None = None
        for width in (2, 1):
            if len(tokens) < width:
                continue
            phrase = " ".join(tokens[-width:])
            if phrase.lower() in _MODEL_OTHER_TOKENS:
                continue
            if phrase.lower() in lex:
                removed = phrase
                tokens = tokens[:-width]
                break
        if not removed:
            break
        found.append(removed)
    return " ".join(tokens).strip()

def _material_flex(pattern: str) -> str:
    return re.escape(pattern).replace(r"\ ", r"\s+")


def _compile_material_patterns() -> list[tuple[str, re.Pattern[str], re.Pattern[str], re.Pattern[str]]]:
    """返回 (canonical, word, prefix, suffix) 正则元组，按材质名长度降序。"""
    compiled: list[tuple[str, re.Pattern[str], re.Pattern[str], re.Pattern[str]]] = []
    for pat in sorted(_MATERIAL_PATTERNS, key=len, reverse=True):
        flex = _material_flex(pat)
        compiled.append(
            (
                pat,
                re.compile(rf"\b{flex}\b", re.IGNORECASE),
                re.compile(rf"^{flex}(?:\s+|$)", re.IGNORECASE),
                re.compile(rf"(?:\s+){flex}$", re.IGNORECASE),
            )
        )
    return compiled


_MATERIAL_RES = _compile_material_patterns()


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fuzzy_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def _fuzzy_equal(left: str, right: str, *, threshold: float = _FUZZY_THRESHOLD) -> bool:
    if left.lower() == right.lower():
        return True
    return _fuzzy_ratio(left, right) >= threshold


def _fuzzy_match_key(text: str, candidates: dict[str, Any], *, threshold: float = _FUZZY_THRESHOLD) -> str | None:
    key = text.strip().lower()
    if key in candidates:
        return key
    best_key: str | None = None
    best_score = threshold
    for candidate in candidates:
        score = _fuzzy_ratio(key, candidate)
        if score >= best_score:
            best_score = score
            best_key = candidate
    return best_key


def _parse_listish(value: str) -> str | None:
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return text
        if isinstance(parsed, list):
            parts = [str(item).strip() for item in parsed if str(item).strip()]
            return parts[0] if parts else None
        if isinstance(parsed, str):
            return parsed.strip() or None
    return text


def normalize_brand(value: str | None) -> str | None:
    """品牌：去掉列表格式，并归一化为英文标准写法。"""
    text = _clean_text(value)
    if not text:
        return None
    parsed = _parse_listish(text)
    return normalize_brand_english(parsed)


def _normalize_condition_key(value: str) -> str:
    text = value.strip()
    if text.startswith("bc-filter-"):
        text = text.removeprefix("bc-filter-")
    text = _parse_listish(text) or text
    return re.sub(r"\s+", " ", text.strip().lower())


def format_condition_grade(value: str | None) -> str | None:
    """成色判断：如 99新/Excellent；支持模糊匹配英文成色。"""
    text = _clean_text(value)
    if not text:
        return None
    if "/" in text and any(ch.isdigit() or "\u4e00" <= ch <= "\u9fff" for ch in text.split("/", 1)[0]):
        return text
    key = _normalize_condition_key(text)
    mapped_key = _fuzzy_match_key(key, _CONDITION_GRADES)
    if mapped_key:
        cn, en = _CONDITION_GRADES[mapped_key]
        return f"{cn}/{en}"
    original = _parse_listish(text) or text
    return original


def extract_year(*texts: str | None) -> str | None:
    """仅识别飞书同款爱马仕刻印；竞品英文标题无刻印时返回 None，不猜测年份。"""
    for raw in texts:
        text = _clean_text(raw)
        if not text:
            continue
        padded = f" {text} "
        for pattern in _HERMES_YEAR_RES:
            match = pattern.search(padded)
            if match:
                return match.group(1).strip()
    return None


def _color_parts(color: str | None) -> list[str]:
    if not color:
        return []
    return [part.strip() for part in color.split("/") if part.strip()]


def _strip_phrases_anywhere(text: str, phrases: tuple[str, ...]) -> str:
    result = text
    for phrase in phrases:
        flex = _material_flex(phrase)
        result = re.sub(rf"\b{flex}\b", " ", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def _cleanup_model_junk(text: str) -> str:
    """仅去掉首尾孤立连接词，保留款式名中间的 and（如 Plated Metal and Leather）。"""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:and|with|in)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:and|with|in)\s*$", "", text, flags=re.IGNORECASE)
    return text


_FALLBACK_BRAND_PREFIXES: tuple[str, ...] = (
    "Louis Vuitton",
    "Bottega Veneta",
    "Hermès",
    "Hermes",
    "Chanel",
    "Gucci",
    "Prada",
    "Fendi",
    "Celine",
    "Céline",
    "Dior",
    "Loewe",
)


def _strip_leading_brand(text: str, brand: str | None) -> str:
    """去掉型号字段中重复出现的品牌前缀（如 Hermes Birkin 35）。"""
    if not text:
        return text
    work = text.strip()
    candidates: list[str] = []
    if brand:
        candidates.append(brand)
        if "hermes" in brand.lower():
            candidates.extend(["Hermes", "Hermès"])
    candidates.extend(_FALLBACK_BRAND_PREFIXES)
    seen: set[str] = set()
    for name in candidates:
        key = name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        flex = _material_flex(name.strip())
        work = re.sub(rf"^{flex}\s+", "", work, flags=re.IGNORECASE).strip()
    return work


def _strip_color_from_model(model: str, color: str | None) -> tuple[str, list[str]]:
    """从型号任意位置剔除颜色词；返回 (净型号, 从型号中剔出的颜色片段)。"""
    if not model:
        return model, []
    text = model.strip()
    found: list[str] = []

    for part in _color_parts(color):
        flex = _material_flex(part)
        if re.search(rf"\b{flex}\b", text, flags=re.IGNORECASE):
            found.append(part)
            text = re.sub(rf"\b{flex}\b", " ", text, flags=re.IGNORECASE)

    for phrase in _color_strip_phrases():
        if phrase.lower() in _MODEL_OTHER_TOKENS:
            continue
        flex = _material_flex(phrase)
        if not re.search(rf"\b{flex}\b", text, flags=re.IGNORECASE):
            continue
        if phrase.lower() == "quartz" and _COLOR_STRIP_GUARD_RE.search(text):
            continue
        found.append(phrase)
        text = re.sub(rf"\b{flex}\b", " ", text, flags=re.IGNORECASE)

    if color:
        tokens = text.split()
        for width in range(min(len(tokens), 3), 0, -1):
            suffix = " ".join(tokens[-width:])
            for part in _color_parts(color):
                if suffix.lower() == part.lower() or _fuzzy_equal(suffix, part):
                    found.append(part)
                    text = " ".join(tokens[:-width]).strip()
                    break
            if text != " ".join(tokens):
                break

    text = _strip_trailing_lexicon_colors(text, found)
    text = _cleanup_model_junk(text)
    return text, found


def _strip_condition_from_model(model: str, condition: str | None) -> tuple[str, str | None]:
    """从型号任意位置剔除成色词。"""
    if not model:
        return model, None
    text = model.strip()
    found: str | None = None

    text = _strip_phrases_anywhere(text, _CONDITION_STRIP_PHRASES)
    edge = _CONDITION_EDGE_RE.search(text)
    if edge:
        found = edge.group(0).strip()
        text = _CONDITION_EDGE_RE.sub(" ", text)

    if condition:
        cond_key = _normalize_condition_key(condition)
        for phrase in _CONDITION_STRIP_PHRASES:
            if _normalize_condition_key(phrase) == cond_key or phrase.lower() in cond_key:
                flex = _material_flex(phrase)
                if re.search(rf"\b{flex}\b", model, flags=re.IGNORECASE):
                    found = found or phrase
                break

    text = _cleanup_model_junk(text)
    return text, found


def _strip_color_suffix(model: str, color: str | None) -> str:
    """兼容旧逻辑：尾部去色 + 全句扫色。"""
    text, _ = _strip_color_from_model(model, color)
    return text


def strip_color_condition_from_model(
    model: str | None,
    *,
    color: str | None = None,
    condition: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """
    从型号中剥离颜色/成色；若对应列为空则返回剔出的值供回填。
    返回 (净型号, 可回填颜色, 可回填成色)。
    """
    text = _clean_text(model)
    if not text:
        return None, None, None

    text, stripped_cond = _strip_condition_from_model(text, condition)
    text, stripped_colors = _strip_color_from_model(text, color)

    backfill_color: str | None = None
    if stripped_colors:
        backfill_color = stripped_colors[0] if len(stripped_colors) == 1 else "/".join(stripped_colors)

    backfill_condition: str | None = None
    if stripped_cond and not _clean_text(condition):
        backfill_condition = stripped_cond

    return text or None, backfill_color, backfill_condition


def _remove_match(text: str, match: re.Match[str]) -> str:
    remainder = (text[: match.start()] + " " + text[match.end() :]).strip()
    return re.sub(r"\s+", " ", remainder)


def _find_embedded_material(text: str) -> tuple[str, str] | None:
    """嵌入匹配：最长材质词优先。"""
    best: tuple[str, str, int, int] | None = None
    for canonical, word_re, _, _ in _MATERIAL_RES:
        match = word_re.search(text)
        if not match:
            continue
        remainder = _remove_match(text, match)
        if not remainder:
            continue
        candidate = (canonical, remainder, len(canonical), match.start())
        if best is None or candidate[2] > best[2] or (candidate[2] == best[2] and candidate[3] < best[3]):
            best = candidate
    if best is None:
        return None
    return best[0], best[1]


def _extract_material(model: str) -> tuple[str | None, str]:
    """材质：正则前缀 → 嵌入 → 后缀；取最长匹配。"""
    text = re.sub(r"\s+", " ", model.strip())
    if not text:
        return None, text

    for canonical, _, prefix_re, suffix_re in _MATERIAL_RES:
        match = prefix_re.match(text)
        if match:
            return canonical, text[match.end() :].strip()

    embedded = _find_embedded_material(text)
    if embedded:
        return embedded

    for canonical, _, _, suffix_re in _MATERIAL_RES:
        match = suffix_re.search(text)
        if match:
            return canonical, text[: match.start()].strip()

    return None, text


def _strip_phrases(text: str, phrases: tuple[str, ...]) -> str:
    result = text
    for phrase in sorted(phrases, key=len, reverse=True):
        flex = _material_flex(phrase)
        result = re.sub(rf"\s+{flex}\s+", " ", result, flags=re.IGNORECASE)
        result = re.sub(rf"\s+{flex}$", "", result, flags=re.IGNORECASE)
        result = re.sub(rf"^{flex}\s+", "", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def _strip_residual_material(text: str, material: str | None) -> str:
    """去掉型号中残留、且已在 material 列出现的材质词。"""
    result = text
    if material:
        flex = _material_flex(material)
        result = re.sub(rf"\s+{flex}\s+", " ", result, flags=re.IGNORECASE)
        result = re.sub(rf"\s+{flex}$", "", result, flags=re.IGNORECASE)
        result = re.sub(rf"^{flex}\s+", "", result, flags=re.IGNORECASE)
    embedded = _find_embedded_material(result)
    if embedded:
        _, result = embedded
    return re.sub(r"\s+", " ", result).strip()


def _is_size_token(token: str) -> bool:
    return bool(_SIZE_TOKEN_RE.match(token.strip()))


def _extract_model_size_tokens(tokens: list[str]) -> tuple[list[str], str | None]:
    """从尾部提取尺码（支持 Mini、25、BB 等）。"""
    if not tokens:
        return tokens, None
    size_parts: list[str] = []
    work = list(tokens)
    while work and len(size_parts) < 2:
        last = work[-1]
        if _is_size_token(last):
            size_parts.insert(0, last)
            work.pop()
            continue
        break
    if not size_parts:
        return tokens, None
    return work, " ".join(size_parts)


def _normalize_model_compact(name: str) -> str:
    """Kelly28 → Kelly 28（仅处理无空格的连写）。"""
    text = name.strip()
    if " " in text:
        return text
    match = _ALPHA_NUM_MODEL_RE.match(text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return text


def _compose_model(series: str | None, size: str | None) -> str | None:
    if series and size:
        return f"{series} {size}"
    return series or size


def _token_key(token: str) -> str:
    return _fold_accents(token).lower()


def _is_hermes_line_token(token: str) -> bool:
    key = _token_key(token)
    return key in _HERMES_LINE_NAMES


def _model_has_hermes_line(model_l: str) -> bool:
    if "24/24" in model_l:
        return True
    tokens = model_l.split()
    return any(t in _HERMES_LINE_NAMES for t in tokens)


def _split_other_parts(cleaned: str) -> list[str]:
    parts: list[str] = []
    for chunk in re.split(r"\s*/\s*", cleaned):
        chunk = chunk.strip()
        if not chunk:
            continue
        key = _token_key(chunk)
        parts.append(key)
    return parts


def _merge_other_values(*values: str | None) -> str | None:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        for part in _split_other_parts(value):
            if part and part not in seen:
                seen.add(part)
                merged.append(part)
    return "/".join(merged) if merged else None


def _split_slash_parts(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("/") if part.strip()]


def _merge_color_field(*values: str | None) -> str | None:
    """合并颜色列与从型号拆解出的颜色，去重后用 / 连接。"""
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in _split_slash_parts(value):
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            parts.append(part)
    if not parts:
        return None
    return normalize_color("/".join(parts))


def _merge_material_field(*values: str | None) -> str | None:
    """合并材质列与从型号拆解出的材质，去重后用 / 连接。"""
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in _split_slash_parts(value):
            normalized = normalize_material_english(part)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            parts.append(normalized)
    return "/".join(parts) if parts else None


def split_model_other(text: str | None) -> tuple[str | None, str | None]:
    """
    从型号中剥离工艺/结构修饰（如 Kelly Sellier 28 → Kelly 28 + sellier）。
    仅当修饰词紧跟已知款式线时剥离，避免误伤 Elsa Sellier 等款式名。
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return None, None

    other: list[str] = []
    work = cleaned

    if work.lower().startswith("so black "):
        other.append("so black")
        work = work[9:].strip()

    tokens = work.split()
    if not tokens:
        return None, _merge_other_values("/".join(other) if other else None)

    if _token_key(tokens[0]) == "touch" and len(tokens) > 1 and _is_hermes_line_token(tokens[1]):
        other.append("touch")
        tokens = tokens[1:]

    if (
        len(tokens) >= 2
        and _token_key(tokens[0]) == "cargo"
        and _token_key(tokens[1]) == "picotin"
    ):
        other.append("cargo")
        tokens = tokens[1:]

    kept: list[str] = []
    for i, token in enumerate(tokens):
        key = _token_key(token)
        if key not in _MODEL_OTHER_TOKENS:
            kept.append(token)
            continue

        prev_key = _token_key(tokens[i - 1]) if i > 0 else ""
        line_key = _token_key(kept[-1]) if kept else prev_key
        kept_has_line = any(_is_hermes_line_token(t) for t in kept)

        if key == "faubourg":
            if prev_key == "barenia" or line_key in _HERMES_LINE_NAMES or kept_has_line:
                other.append(key)
                continue
        elif key == "cargo":
            if line_key == "picotin" or any(_token_key(t) == "picotin" for t in kept):
                other.append(key)
                continue
        elif line_key in _HERMES_LINE_NAMES:
            other.append(key)
            continue

        kept.append(token)

    model = " ".join(kept).strip() or None
    other_val = _merge_other_values("/".join(other) if other else None)
    return model, other_val


def _sanitize_model_other(model: str | None, other: str | None) -> tuple[str | None, str | None]:
    """将误拆进 other 的款式词合并回 model；other 已在 model 中出现则丢弃。"""
    work = _clean_text(model)
    cleaned_other = _clean_text(other)
    if not work:
        return work, None
    if not cleaned_other:
        return work, cleaned_other

    model_key = _token_key(work)
    model_tokens = set(model_key.split())
    kept_other: list[str] = []
    for raw_part in re.split(r"\s*/\s*", cleaned_other):
        part = _token_key(raw_part.strip())
        if not part:
            continue
        if part in model_key or part in model_tokens:
            continue
        rejoined = False
        for token, line_keys, position, expand_suffix in _MODEL_OTHER_REJOIN:
            if part != token:
                continue
            if not any(key in model_tokens or key in model_key for key in line_keys):
                continue
            suffix_text = expand_suffix or token
            if position == "prefix" and not model_key.startswith(f"{token} "):
                work = f"{token} {work}".strip()
            elif position == "suffix" and not model_key.endswith(f" {suffix_text}"):
                work = f"{work} {suffix_text}".strip()
            model_key = _token_key(work)
            model_tokens = set(model_key.split())
            rejoined = True
            break
        if not rejoined:
            kept_other.append(part)

    other_val = "/".join(kept_other) if kept_other else None
    return work or None, other_val


def _filter_valid_other(other: str | None, *, model: str | None = None) -> str | None:
    """other 仅保留工艺/结构变体；touch/faubourg 需 Hermès 款式线；cargo 仅 Cargo Picotin。"""
    cleaned = _clean_text(other)
    if not cleaned:
        return None
    model_l = (_clean_text(model) or "").lower()
    valid: list[str] = []
    for p in _split_other_parts(cleaned):
        if p not in _VALID_OTHER_PARTS:
            continue
        if p == "touch" and not _model_has_hermes_line(model_l):
            continue
        if p == "cargo" and "picotin" not in model_l:
            continue
        if p == "faubourg" and not _model_has_hermes_line(model_l):
            continue
        valid.append(p)
    return "/".join(valid) if valid else None


def _strip_redundant_other_prefixes(model: str | None, other: str | None) -> str | None:
    work = _clean_text(model)
    if not work or not other:
        return work
    model_l = work.lower()
    for part in _split_other_parts(other):
        if part == "cargo" and model_l.startswith("cargo picotin"):
            work = work[len("cargo ") :].strip()
            model_l = work.lower()
        if part == "so black" and model_l.startswith("so black "):
            work = work[len("so black ") :].strip()
            model_l = work.lower()
    return work or None


def refine_model_display(
    text: str | None,
    *,
    material: str | None = None,
    color: str | None = None,
    condition: str | None = None,
) -> str | None:
    """将净型号规整为飞书「型号」单列：款式 + 尺码（如 Birkin 35、Alma BB）。"""
    cleaned = _clean_text(text)
    if not cleaned:
        return None

    work = _strip_phrases(cleaned, _BAG_TYPE_PHRASES)
    work = _strip_phrases_anywhere(work, _MODEL_MODIFIER_PHRASES)
    work = _strip_residual_material(work, material)
    work, _, _ = strip_color_condition_from_model(work, color=color, condition=condition)
    if not work:
        work = _normalize_model_compact(cleaned)
        work, _, _ = strip_color_condition_from_model(work, color=color, condition=condition)
    if not work:
        return None

    work = _normalize_model_compact(work)
    tokens = work.split()
    series_tokens, size = _extract_model_size_tokens(tokens)
    series = " ".join(series_tokens).strip() or None
    if series and not size:
        retokens = series.split()
        series_tokens, size = _extract_model_size_tokens(retokens)
        series = " ".join(series_tokens).strip() or None
    return _compose_model(series, size)


def _apply_model_other(
    record: dict[str, Any],
    *,
    model_key: str,
    llm_other: str | None = None,
    source_text: str | None = None,
) -> None:
    """LLM 优先写入 other；误拆词合并回 model；other 仅保留工艺变体。"""
    model = record.get(model_key)
    _, source_other = split_model_other(source_text)
    model, rule_other = split_model_other(model)
    other = _merge_other_values(llm_other, source_other, rule_other)
    model = _strip_redundant_other_prefixes(model, other) or model
    model, other = _sanitize_model_other(model, other)
    other = _filter_valid_other(other, model=model)
    record[model_key] = normalize_name_english(model)
    if other:
        record["other"] = normalize_name_english(other)


def split_fr_model(
    model: str | None,
    color: str | None,
    condition: str | None = None,
    *,
    brand: str | None = None,
) -> tuple[str | None, str | None, str | None, bool, str | None]:
    """从 F/R 原始型号拆分：材质 + 飞书型号 + LLM 色/其他；第四项表示是否采用 LLM。"""
    text = _strip_leading_brand(_clean_text(model) or "", brand)
    if not text:
        return None, None, None, False, None

    semantic_material: str | None = None
    semantic_model: str | None = None
    semantic_color: str | None = None
    semantic_other: str | None = None
    try:
        from src.model_semantics import semantic_parse_model, use_llm_semantics

        if use_llm_semantics():
            parsed = semantic_parse_model(
                text,
                brand=brand,
                color=color,
                condition=condition,
            )
            if parsed and parsed.model:
                semantic_material = parsed.material
                semantic_model = parsed.model
                semantic_color = parsed.color
                semantic_other = parsed.other
    except Exception:
        pass

    if semantic_model:
        return semantic_material, semantic_model, semantic_color, True, semantic_other

    stripped_model, extracted_color, _ = strip_color_condition_from_model(
        text, color=color, condition=condition
    )
    work = stripped_model or text
    material, cleaned = _extract_material(work)
    cleaned = re.sub(r"\s+", " ", cleaned).strip() or work
    display = refine_model_display(
        cleaned, material=material, color=color, condition=condition
    )
    return material, display, extracted_color, False, None


def split_v_product_name(
    product_name: str | None,
    material: str | None,
    *,
    color: str | None = None,
    condition: str | None = None,
    brand: str | None = None,
) -> tuple[str | None, str | None, str | None, bool, str | None]:
    """V 表：型号 + LLM 色/材质/其他；第四项表示是否采用 LLM。"""
    text = _clean_text(product_name)
    if not text:
        return None, None, None, False, None

    semantic_model: str | None = None
    semantic_color: str | None = None
    semantic_material: str | None = None
    semantic_other: str | None = None
    try:
        from src.model_semantics import semantic_parse_model, use_llm_semantics

        if use_llm_semantics():
            parsed = semantic_parse_model(
                text,
                brand=brand,
                color=color,
                condition=condition,
            )
            if parsed and parsed.model:
                semantic_model = parsed.model
                semantic_color = parsed.color
                semantic_material = parsed.material
                semantic_other = parsed.other
    except Exception:
        pass

    if semantic_model:
        return semantic_model, semantic_color, semantic_material, True, semantic_other

    for suffix_re in _V_SUFFIX_RES:
        text = suffix_re.sub("", text).strip()

    if material:
        mat = material.strip()
        if mat:
            escaped = re.escape(mat).replace(r"\ ", r"\s+")
            text = re.sub(rf"\s+{escaped}\s*$", "", text, flags=re.IGNORECASE).strip()
            tokens = text.split()
            if tokens and _fuzzy_equal(tokens[-1], mat):
                text = " ".join(tokens[:-1]).strip()

    pre_display, extracted_color, _ = strip_color_condition_from_model(
        text, color=color, condition=condition
    )
    display = refine_model_display(
        pre_display, material=material, color=color, condition=condition
    )
    return display, extracted_color, None, False, None


def _apply_model_backfill(
    record: dict[str, Any],
    *,
    model_key: str,
    skip_color_from_model: bool = False,
) -> None:
    model = record.get(model_key)
    color = record.get("color")
    condition = record.get("condition")
    if skip_color_from_model:
        text = _clean_text(model)
        if not text:
            return
        text, stripped_cond = _strip_condition_from_model(text, condition)
        record[model_key] = text or None
        if stripped_cond and not _clean_text(condition):
            record["condition"] = format_condition_grade(stripped_cond)
        return

    cleaned, backfill_color, backfill_condition = strip_color_condition_from_model(
        model, color=color, condition=condition
    )
    record[model_key] = cleaned
    if backfill_color:
        record["color"] = _merge_color_field(record.get("color"), backfill_color)
    if not _clean_text(condition) and backfill_condition:
        record["condition"] = format_condition_grade(backfill_condition)


def format_fr_record(record: dict[str, Any]) -> None:
    original_model = record.get("model")
    original_material = record.get("material")
    record["brand"] = normalize_brand(record.get("brand"))
    record["color"] = normalize_color(record.get("color"))
    record["condition"] = format_condition_grade(record.get("condition"))
    material, model, extracted_color, used_llm, llm_other = split_fr_model(
        original_model,
        record.get("color"),
        record.get("condition"),
        brand=record.get("brand"),
    )
    record["material"] = _merge_material_field(original_material, material)
    record["model"] = normalize_name_english(model)
    if extracted_color:
        record["color"] = _merge_color_field(record.get("color"), extracted_color)
    _apply_model_backfill(record, model_key="model", skip_color_from_model=used_llm)
    _apply_model_other(
        record,
        model_key="model",
        llm_other=llm_other if used_llm else None,
        source_text=original_model,
    )
    record["year"] = extract_year(original_model)


def format_v_record(record: dict[str, Any]) -> None:
    record["brand"] = normalize_brand(record.get("brand"))
    record["color"] = normalize_color(record.get("color"))
    record["condition"] = format_condition_grade(record.get("condition"))
    original_name = record.get("product_name")
    product_name, extracted_color, llm_material, used_llm, llm_other = split_v_product_name(
        original_name,
        record.get("material"),
        color=record.get("color"),
        condition=record.get("condition"),
        brand=record.get("brand"),
    )
    record["product_name"] = product_name
    record["material"] = _merge_material_field(record.get("material"), llm_material)
    if extracted_color:
        record["color"] = _merge_color_field(record.get("color"), extracted_color)
    _apply_model_backfill(
        record,
        model_key="product_name",
        skip_color_from_model=used_llm,
    )
    _apply_model_other(
        record,
        model_key="product_name",
        llm_other=llm_other if used_llm else None,
        source_text=original_name,
    )
    record["year"] = extract_year(original_name, record.get("product_name"))


def format_record_from_old_data(
    record: dict[str, Any],
    old_data: dict[str, Any],
    *,
    table_kind: str,
) -> None:
    """用 old_data 中的飞书原值（尤其型号）回填 model/material/year/other 等列。"""
    if table_kind in {"F", "R"}:
        working = {
            "brand": record.get("brand") or old_data.get("brand"),
            "model": old_data.get("model"),
            "condition": record.get("condition") or old_data.get("condition"),
            "color": record.get("color") or old_data.get("color"),
            "material": old_data.get("material"),
            "year": None,
            "other": None,
        }
        format_fr_record(working)
        for key in ("brand", "model", "condition", "color", "material", "year", "other"):
            record[key] = working.get(key)
        return

    working = {
        "brand": record.get("brand") or old_data.get("brand"),
        "product_name": old_data.get("product_name"),
        "material": record.get("material") or old_data.get("material"),
        "condition": record.get("condition") or old_data.get("condition"),
        "color": record.get("color") or old_data.get("color"),
        "year": None,
        "other": None,
    }
    format_v_record(working)
    for key in ("brand", "product_name", "material", "condition", "color", "year", "other"):
        record[key] = working.get(key)


def format_import_light_fr(record: dict[str, Any]) -> None:
    """导入阶段轻量清洗：仅品牌/颜色/成色；保留原始型号供后续 LLM 解析。"""
    record["brand"] = normalize_brand(record.get("brand"))
    record["color"] = normalize_color(record.get("color"))
    record["condition"] = format_condition_grade(record.get("condition"))


def format_import_light_v(record: dict[str, Any]) -> None:
    """导入阶段轻量清洗：仅品牌/颜色/成色；保留原始商品名供后续 LLM 解析。"""
    record["brand"] = normalize_brand(record.get("brand"))
    record["color"] = normalize_color(record.get("color"))
    record["condition"] = format_condition_grade(record.get("condition"))


def format_import_record(record: dict[str, Any], *, table_kind: str) -> None:
    try:
        from src.model_semantics import use_llm_semantics
    except Exception:
        use_llm_semantics = lambda: False  # type: ignore[misc, assignment]

    if use_llm_semantics():
        if table_kind in {"F", "R"}:
            format_import_light_fr(record)
        elif table_kind == "V":
            format_import_light_v(record)
        return

    if table_kind in {"F", "R"}:
        format_fr_record(record)
    elif table_kind == "V":
        format_v_record(record)
