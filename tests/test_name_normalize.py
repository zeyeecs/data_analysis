from __future__ import annotations

import pytest

from src.field_normalize import normalize_color
from src.name_normalize import (
    finalize_english_lower,
    normalize_brand_english,
    normalize_material_english,
    normalize_name_english,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hermès", "hermes"),
        ("Chloé", "chloe"),
        ("Alaïa", "alaia"),
        ("Céline", "celine"),
        ("Non Signé / Unsigned", "non signed / unsigned"),
        ("See by Chloé", "see by chloe"),
        ("Louis Vuitton", "louis vuitton"),
    ],
)
def test_normalize_brand_english(raw: str, expected: str) -> None:
    assert normalize_brand_english(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Noé", "noe"),
        ("NéoNoé BB", "neonoe bb"),
        ("Speedy Bandoulière", "speedy bandouliere"),
        ("Le 5 à 7", "le 5 a 7"),
        ("Multi Pochette Accessoires", "multi pochette accessories"),
        ("Bum Bag Sac Ceinture", "bum bag belt bag"),
        ("Félicie", "felicie"),
        ("Sac 16", "sac 16"),
        ("CITY", "city"),
        ("框R/2014", "框R/2014"),
        (None, None),
    ],
)
def test_normalize_name_english(raw: str | None, expected: str | None) -> None:
    assert normalize_name_english(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cuir", "leather"),
        ("Toile et cuir", "canvas and leather"),
        ("vegan cuir", "vegan leather"),
        ("peau de veau", "calfskin"),
        ("Pony-style calfskin", "pony-style calfskin"),
        ("Leather", "leather"),
    ],
)
def test_normalize_material_english(raw: str, expected: str) -> None:
    assert normalize_material_english(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("noir", "black"),
        ("Rouge", "red"),
        ("doré", "gold"),
        ("Gris/Noir", "black/gray"),
        ("BLACK", "black"),
    ],
)
def test_normalize_color_french(raw: str, expected: str) -> None:
    assert normalize_color(raw) == expected


def test_finalize_english_lower_preserves_chinese() -> None:
    assert finalize_english_lower("框R/2014") == "框R/2014"
