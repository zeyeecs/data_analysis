#!/usr/bin/env python3
"""将 V 表 USD 价格按当前中间价换算为 CNY，并统一 currency 列。"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.currency_convert import CNY_CURRENCY, fetch_usd_cny_rate
from src.db import db_session

load_config()


def _count_by_currency(cur) -> list[tuple[str | None, int]]:
    cur.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(currency), ''), '(null)') AS c, COUNT(*)::int
        FROM "V"
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )
    return cur.fetchall()


def _apply(cur, rate: Decimal, *, dry_run: bool) -> int:
    cur.execute(
        """
        SELECT COUNT(*)::int FROM "V"
        WHERE UPPER(TRIM(currency)) = 'USD'
        """
    )
    pending = cur.fetchone()[0]
    if pending == 0 or dry_run:
        return pending

    cur.execute(
        """
        UPDATE "V"
        SET
            price = ROUND(price * %s, 2),
            seller_price = CASE
                WHEN seller_price IS NOT NULL THEN ROUND(seller_price * %s, 2)
                ELSE NULL
            END,
            buyer_fee = CASE
                WHEN buyer_fee IS NOT NULL THEN ROUND(buyer_fee * %s, 2)
                ELSE NULL
            END,
            currency = %s
        WHERE UPPER(TRIM(currency)) = 'USD'
        """,
        (rate, rate, rate, CNY_CURRENCY),
    )
    return cur.rowcount


def _normalize_cny_aliases(cur, *, dry_run: bool) -> int:
    cur.execute(
        """
        SELECT COUNT(*)::int FROM "V"
        WHERE currency IS NOT NULL
          AND TRIM(currency) <> ''
          AND NOT (UPPER(TRIM(currency)) = 'USD')
          AND currency <> %s
        """,
        (CNY_CURRENCY,),
    )
    pending = cur.fetchone()[0]
    if pending == 0 or dry_run:
        return pending

    # 仅将 RMB/人民币 等别名统一为 CNY，不改动价格
    cur.execute(
        """
        UPDATE "V"
        SET currency = %s
        WHERE currency IS NOT NULL
          AND TRIM(currency) <> ''
          AND NOT (UPPER(TRIM(currency)) = 'USD')
          AND (
            UPPER(TRIM(currency)) IN ('RMB', 'CN¥')
            OR TRIM(currency) IN ('人民币', '元', '¥')
          )
        """,
        (CNY_CURRENCY,),
    )
    return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="V 表货币统一为 CNY")
    parser.add_argument(
        "--rate",
        type=str,
        help="USD→CNY 汇率（默认拉取公开中间价）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计待换算行数，不写库",
    )
    args = parser.parse_args()

    rate = Decimal(args.rate) if args.rate else fetch_usd_cny_rate()
    print(f"USD→CNY 汇率: {rate}", flush=True)

    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            print("换算前 currency 分布:", flush=True)
            for c, n in _count_by_currency(cur):
                print(f"  {c}: {n:,}", flush=True)

            usd_rows = _apply(cur, rate, dry_run=args.dry_run)
            alias_rows = _normalize_cny_aliases(cur, dry_run=args.dry_run)

            if args.dry_run:
                print(f"dry-run: 将换算 USD 行 {usd_rows:,}，将规范化 CNY 别名 {alias_rows:,}", flush=True)
            else:
                print(f"已换算 USD→CNY: {usd_rows:,} 行", flush=True)
                if alias_rows:
                    print(f"已规范化 currency 别名: {alias_rows:,} 行", flush=True)

            print("换算后 currency 分布:", flush=True)
            for c, n in _count_by_currency(cur):
                print(f"  {c}: {n:,}", flush=True)

            cur.execute(
                """
                SELECT COUNT(*)::int FROM "V"
                WHERE currency IS NOT NULL
                  AND TRIM(currency) <> ''
                  AND UPPER(TRIM(currency)) <> %s
                """,
                (CNY_CURRENCY,),
            )
            leftover = cur.fetchone()[0]
            if leftover:
                cur.execute(
                    """
                    SELECT DISTINCT currency FROM "V"
                    WHERE currency IS NOT NULL
                      AND TRIM(currency) <> ''
                      AND UPPER(TRIM(currency)) <> %s
                    LIMIT 20
                    """,
                    (CNY_CURRENCY,),
                )
                others = [r[0] for r in cur.fetchall()]
                print(f"警告: 仍有 {leftover} 行非 CNY: {others}", flush=True)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
