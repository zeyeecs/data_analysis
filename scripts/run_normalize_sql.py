#!/usr/bin/env python3
"""逐条执行规范化 SQL（可重复执行，遇死锁自动重试）。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2

from src.config import load_config
from src.db import get_connection

load_config()

STEPS: list[tuple[str, str]] = [
    (
        "F: 单元素 color 列表",
        """UPDATE "F"
SET color = (regexp_match(color, '^\\[''([^'']+)''\\]$'))[1]
WHERE color ~ '^\\[''[^'']+''\\]$'""",
    ),
    (
        "F: 空 color 列表",
        'UPDATE "F" SET color = NULL WHERE color = \'[]\'',
    ),
    (
        "F: color 别名",
        """UPDATE "F" SET color = CASE lower(color)
    WHEN 'beige' THEN 'Beige' WHEN 'black' THEN 'Black' WHEN 'blue' THEN 'Blue'
    WHEN 'blues' THEN 'Blue' WHEN 'brown' THEN 'Brown' WHEN 'browns' THEN 'Brown'
    WHEN 'gold' THEN 'Gold' WHEN 'gray' THEN 'Gray' WHEN 'grays' THEN 'Gray'
    WHEN 'grey' THEN 'Gray' WHEN 'greys' THEN 'Gray' WHEN 'green' THEN 'Green'
    WHEN 'greens' THEN 'Green' WHEN 'khaki' THEN 'Khaki' WHEN 'metallic' THEN 'Metallic'
    WHEN 'multicolor' THEN 'Multicolor' WHEN 'multicolour' THEN 'Multicolor'
    WHEN 'neutral' THEN 'Neutral' WHEN 'orange' THEN 'Orange' WHEN 'pink' THEN 'Pink'
    WHEN 'print' THEN 'Print' WHEN 'purple' THEN 'Purple' WHEN 'purples' THEN 'Purple'
    WHEN 'red' THEN 'Red' WHEN 'reds' THEN 'Red' WHEN 'silver' THEN 'Silver'
    WHEN 'white' THEN 'White' WHEN 'whites' THEN 'White' WHEN 'yellow' THEN 'Yellow'
    WHEN 'yellows' THEN 'Yellow' WHEN 'color' THEN NULL ELSE initcap(color) END
WHERE color IS NOT NULL AND color <> '' AND color NOT LIKE '[%'""",
    ),
    (
        "R: color 别名",
        """UPDATE "R" SET color = CASE lower(color)
    WHEN 'beige' THEN 'Beige' WHEN 'black' THEN 'Black' WHEN 'blue' THEN 'Blue'
    WHEN 'blues' THEN 'Blue' WHEN 'brown' THEN 'Brown' WHEN 'browns' THEN 'Brown'
    WHEN 'gold' THEN 'Gold' WHEN 'gray' THEN 'Gray' WHEN 'grays' THEN 'Gray'
    WHEN 'grey' THEN 'Gray' WHEN 'greys' THEN 'Gray' WHEN 'green' THEN 'Green'
    WHEN 'greens' THEN 'Green' WHEN 'khaki' THEN 'Khaki' WHEN 'metallic' THEN 'Metallic'
    WHEN 'multicolor' THEN 'Multicolor' WHEN 'multicolour' THEN 'Multicolor'
    WHEN 'neutral' THEN 'Neutral' WHEN 'orange' THEN 'Orange' WHEN 'pink' THEN 'Pink'
    WHEN 'print' THEN 'Print' WHEN 'purple' THEN 'Purple' WHEN 'purples' THEN 'Purple'
    WHEN 'red' THEN 'Red' WHEN 'reds' THEN 'Red' WHEN 'silver' THEN 'Silver'
    WHEN 'white' THEN 'White' WHEN 'whites' THEN 'White' WHEN 'yellow' THEN 'Yellow'
    WHEN 'yellows' THEN 'Yellow' WHEN 'color' THEN NULL ELSE initcap(color) END
WHERE color IS NOT NULL AND color <> ''""",
    ),
    (
        "V: color 别名",
        """UPDATE "V" SET color = CASE lower(color)
    WHEN 'beige' THEN 'Beige' WHEN 'black' THEN 'Black' WHEN 'blue' THEN 'Blue'
    WHEN 'blues' THEN 'Blue' WHEN 'brown' THEN 'Brown' WHEN 'browns' THEN 'Brown'
    WHEN 'gold' THEN 'Gold' WHEN 'gray' THEN 'Gray' WHEN 'grays' THEN 'Gray'
    WHEN 'grey' THEN 'Gray' WHEN 'greys' THEN 'Gray' WHEN 'green' THEN 'Green'
    WHEN 'greens' THEN 'Green' WHEN 'khaki' THEN 'Khaki' WHEN 'metallic' THEN 'Metallic'
    WHEN 'multicolor' THEN 'Multicolor' WHEN 'multicolour' THEN 'Multicolor'
    WHEN 'neutral' THEN 'Neutral' WHEN 'orange' THEN 'Orange' WHEN 'pink' THEN 'Pink'
    WHEN 'print' THEN 'Print' WHEN 'purple' THEN 'Purple' WHEN 'purples' THEN 'Purple'
    WHEN 'red' THEN 'Red' WHEN 'reds' THEN 'Red' WHEN 'silver' THEN 'Silver'
    WHEN 'white' THEN 'White' WHEN 'whites' THEN 'White' WHEN 'yellow' THEN 'Yellow'
    WHEN 'yellows' THEN 'Yellow' WHEN 'color' THEN NULL ELSE initcap(color) END
WHERE color IS NOT NULL AND color <> ''""",
    ),
]


def _run_step(cur, conn, name: str, sql: str, retries: int = 5) -> None:
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
            conn.commit()
            print(f"  ok {cur.rowcount:,} rows ({time.time() - t0:.1f}s)", flush=True)
            return
        except psycopg2.errors.DeadlockDetected:
            conn.rollback()
            if attempt == retries:
                raise
            wait = attempt * 3
            print(f"  deadlock, retry {attempt}/{retries} in {wait}s...", flush=True)
            time.sleep(wait)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="逐条执行规范化 SQL")
    parser.add_argument(
        "--condition-only",
        action="store_true",
        help="已废弃：成色不再做档位映射",
    )
    parser.add_argument(
        "start",
        nargs="?",
        type=int,
        default=1,
        help="从第几步开始（1-based）",
    )
    args = parser.parse_args()

    if args.condition_only:
        print("成色已改为保留飞书原始值，无 condition 规范化步骤。", flush=True)
        return 0

    steps = STEPS
    start = max(1, args.start)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for i, (name, sql) in enumerate(steps, 1):
                if i < start:
                    continue
                print(f"[{i}/{len(steps)}] {name}", flush=True)
                _run_step(cur, conn, name, sql)
    finally:
        conn.close()
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
