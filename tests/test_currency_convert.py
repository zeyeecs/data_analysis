from __future__ import annotations

from decimal import Decimal

import pytest

from src.currency_convert import (
    convert_usd_to_cny,
    is_cny_currency,
    normalize_v_record_currency,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CNY", True),
        ("cny", True),
        ("RMB", True),
        ("人民币", True),
        ("USD", False),
        (None, False),
        ("", False),
    ],
)
def test_is_cny_currency(raw: str | None, expected: bool) -> None:
    assert is_cny_currency(raw) is expected


def test_convert_usd_to_cny() -> None:
    rate = Decimal("7")
    assert convert_usd_to_cny(Decimal("100"), rate) == Decimal("700.00")
    assert convert_usd_to_cny(None, rate) is None


def test_normalize_v_record_usd() -> None:
    row = {
        "price": Decimal("100"),
        "seller_price": Decimal("90"),
        "buyer_fee": Decimal("10"),
        "currency": "USD",
    }
    normalize_v_record_currency(row, rate=Decimal("6.5"))
    assert row["currency"] == "CNY"
    assert row["price"] == Decimal("650.00")
    assert row["seller_price"] == Decimal("585.00")
    assert row["buyer_fee"] == Decimal("65.00")


def test_normalize_v_record_already_cny() -> None:
    row = {"price": Decimal("100"), "currency": "RMB"}
    normalize_v_record_currency(row, rate=Decimal("6.5"))
    assert row["currency"] == "CNY"
    assert row["price"] == Decimal("100")
