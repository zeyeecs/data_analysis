from __future__ import annotations

import pytest

from src.field_normalize import normalize_color, normalize_condition


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("New", "New"),
        ("Never worn", "Never worn"),
        ("95新", "95新"),
        ("全新", "全新"),
        ("bc-filter-Great", "bc-filter-Great"),
        ("['Excellent']", "['Excellent']"),
        ("", None),
        (None, None),
        ("  trimmed  ", "trimmed"),
    ],
)
def test_normalize_condition(raw: str | None, expected: str | None) -> None:
    assert normalize_condition(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("black", "black"),
        ("Black", "black"),
        ("['Black']", "black"),
        ("['Browns']", "brown"),
        ("['Browns', 'Multicolor']", "brown/multicolor"),
        ("Multicolour", "multicolor"),
        ("multicolor", "multicolor"),
        ("Grey", "gray"),
        ("[]", None),
        ("color", None),
        ("Black/Multicolor", "black/multicolor"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_color(raw: str | None, expected: str | None) -> None:
    assert normalize_color(raw) == expected
