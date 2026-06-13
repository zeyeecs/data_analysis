"""V 表货币统一为 CNY；USD 按公开中间价换算。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from typing import Any

CNY_CURRENCY = "CNY"

_CNY_ALIASES = frozenset(
    {
        "CNY",
        "RMB",
        "CN¥",
        "¥",
        "人民币",
        "元",
    }
)

# open.er-api.com 无密钥；失败时回退（2026-05-25 约 6.8016）
_FALLBACK_USD_CNY = Decimal("6.801586")
_RATE_API = "https://open.er-api.com/v6/latest/USD"


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_cny_currency(currency: str | None) -> bool:
    if currency is None:
        return False
    text = str(currency).strip()
    if not text:
        return False
    upper = text.upper()
    if upper in _CNY_ALIASES:
        return True
    return text in _CNY_ALIASES


@lru_cache(maxsize=1)
def fetch_usd_cny_rate() -> Decimal:
    """拉取当前 USD→CNY 中间价；网络失败时用回退汇率（进程内缓存）。"""
    try:
        with urllib.request.urlopen(_RATE_API, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError):
        return _FALLBACK_USD_CNY
    rate = data.get("rates", {}).get("CNY")
    if rate is None:
        return _FALLBACK_USD_CNY
    return Decimal(str(rate))


def convert_usd_to_cny(amount: Decimal | None, rate: Decimal) -> Decimal | None:
    if amount is None:
        return None
    return _quantize_money(amount * rate)


def normalize_v_record_currency(
    record: dict[str, Any],
    *,
    rate: Decimal | None = None,
) -> dict[str, Any]:
    """将 V 行价格字段统一为 CNY；已是 CNY 时仅规范化 currency 列。"""
    currency = record.get("currency")
    if is_cny_currency(currency):
        record["currency"] = CNY_CURRENCY
        return record

    cur = (str(currency).strip().upper() if currency else "") or ""
    if cur != "USD":
        return record

    fx = rate if rate is not None else fetch_usd_cny_rate()
    for field in ("price", "seller_price", "buyer_fee"):
        val = record.get(field)
        if isinstance(val, Decimal):
            record[field] = convert_usd_to_cny(val, fx)
    record["currency"] = CNY_CURRENCY
    return record
