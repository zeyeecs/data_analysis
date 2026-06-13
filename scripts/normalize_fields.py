#!/usr/bin/env python3
"""回填 F / R / V 表中已有的 color、condition 为统一格式。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from psycopg2.extras import execute_values

from src.config import load_config
from src.db import get_connection
from src.field_normalize import normalize_color, normalize_condition

load_config()

TABLES = ("F", "R", "V")
READ_BATCH = 5000
WRITE_BATCH = 1000


def _run_sql_migration() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_normalize_sql.py")],
        check=True,
    )


def _bulk_update_condition(cur, table: str, updates: list[tuple[str | None, int]]) -> None:
    if not updates:
        return
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET condition = v.condition
        FROM (VALUES %s) AS v(id, condition)
        WHERE t.id = v.id
        """,
        updates,
        page_size=WRITE_BATCH,
    )


def _bulk_update(cur, table: str, updates: list[tuple[str | None, str | None, int]]) -> None:
    if not updates:
        return
    rows = [(row_id, new_color, new_condition) for new_color, new_condition, row_id in updates]
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET color = v.color, condition = v.condition
        FROM (VALUES %s) AS v(id, color, condition)
        WHERE t.id = v.id
        """,
        rows,
        page_size=WRITE_BATCH,
    )


def _python_pass(table: str, *, dry_run: bool, condition_only: bool) -> tuple[int, int]:
    read_conn = get_connection()
    write_conn = None if dry_run else get_connection()
    scanned = 0
    changed = 0
    last_id = 0

    try:
        with read_conn.cursor() as read_cur:
            read_cur.execute("SET statement_timeout = 0")
            while True:
                if condition_only:
                    read_cur.execute(
                        f"""
                        SELECT id, color, condition
                        FROM "{table}"
                        WHERE id > %s
                        ORDER BY id
                        LIMIT %s
                        """,
                        (last_id, READ_BATCH),
                    )
                else:
                    read_cur.execute(
                        f"""
                        SELECT id, color, condition
                        FROM "{table}"
                        WHERE id > %s
                          AND color IS NOT NULL
                          AND color <> ''
                          AND color ~ '^\['
                        ORDER BY id
                        LIMIT %s
                        """,
                        (last_id, READ_BATCH),
                    )
                rows = read_cur.fetchall()
                if not rows:
                    break

                last_id = int(rows[-1][0])
                color_updates: list[tuple[str | None, str | None, int]] = []
                condition_updates: list[tuple[str | None, int]] = []

                for row_id, color, condition in rows:
                    scanned += 1
                    new_condition = normalize_condition(condition) or condition
                    if condition_only:
                        if new_condition != condition:
                            changed += 1
                            condition_updates.append((new_condition, int(row_id)))
                        continue

                    new_color = normalize_color(color)
                    if new_color != color or new_condition != condition:
                        changed += 1
                        color_updates.append((new_color, new_condition, int(row_id)))

                if write_conn is not None:
                    with write_conn.cursor() as write_cur:
                        write_cur.execute("SET statement_timeout = 0")
                        if condition_only:
                            _bulk_update_condition(write_cur, table, condition_updates)
                        else:
                            _bulk_update(write_cur, table, color_updates)
                    write_conn.commit()

                if scanned % 5000 == 0 or not rows:
                    label = "condition" if condition_only else "python"
                    print(f"  {table} ({label}): scanned {scanned:,}, changed {changed:,}", flush=True)
    finally:
        read_conn.close()
        if write_conn is not None:
            write_conn.close()

    return scanned, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="统一 color / condition 存储格式")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计 Python 补扫将变更的行数（仍会执行 SQL 预览需加 --sql-only）",
    )
    parser.add_argument(
        "--sql-only",
        action="store_true",
        help="仅执行 SQL 批量规范化",
    )
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="跳过 SQL，仅 Python 补扫（F 多色列表等）",
    )
    parser.add_argument(
        "--condition-only",
        action="store_true",
        help="已废弃：成色不再做档位映射",
    )
    parser.add_argument(
        "--table",
        choices=TABLES,
        help="Python 补扫时只处理指定表",
    )
    args = parser.parse_args()

    if args.condition_only:
        print("成色已改为保留飞书原始值，跳过 condition 规范化。", flush=True)
        return 0

    if not args.python_only and not args.dry_run:
        print("running SQL migration...", flush=True)
        _run_sql_migration()
        print("SQL migration done", flush=True)

    if args.sql_only:
        return 0

    targets = (args.table,) if args.table else TABLES
    total_rows = 0
    total_changed = 0

    print("python pass for complex F color lists...", flush=True)
    for table in targets:
        if table != "F" and not args.table:
            continue
        if table != "F":
            continue
        scanned, changed = _python_pass(table, dry_run=args.dry_run, condition_only=False)
        total_rows += scanned
        total_changed += changed
        mode = "would update" if args.dry_run else "updated"
        print(f"{table}: python scanned {scanned:,}, {mode} {changed:,}", flush=True)

    print(f"done: python {total_changed:,} / {total_rows:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
