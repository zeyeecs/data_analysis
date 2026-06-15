#!/usr/bin/env python3
"""回填 F / R / V 商品字段：拆分型号、统一成色判断、规范化品牌/颜色，写入 material / year。"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.product_format_job import TABLES, format_table, run_migration

load_config()


def _parse_snapshot_dates(values: list[str] | None) -> set[date | None] | None:
    if not values:
        return None
    parsed: set[date | None] = set()
    for raw in values:
        text = raw.strip().lower()
        if text in {"null", "none"}:
            parsed.add(None)
            continue
        parsed.add(date.fromisoformat(raw))
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="格式化 F/R/V 商品字段（拆分型号、成色判断等）")
    parser.add_argument("--dry-run", action="store_true", help="只统计将变更的行数，不写库")
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="写入数据库（默认不写库；请先用 scripts/export_format_preview.py 导出本地预览）",
    )
    parser.add_argument("--table", choices=TABLES, help="只处理指定表")
    parser.add_argument("--skip-migration", action="store_true", help="跳过 ADD COLUMN 迁移")
    parser.add_argument(
        "--start-id",
        type=int,
        default=0,
        help="从指定 id 之后继续（断点续跑，仅配合 --table 使用）",
    )
    parser.add_argument(
        "--snapshot-date",
        action="append",
        metavar="DATE",
        help="只处理指定 snapshot_date（可重复；用 null 表示 snapshot_date IS NULL）",
    )
    parser.add_argument(
        "--only-list-brand",
        action="store_true",
        help="仅处理 brand 为列表字面量（如 ['Hermes']）的行，用于每日增量归一化",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.write_db:
        print(
            "error: 未指定 --write-db，不会修改数据库。"
            "请用 scripts/export_format_preview.py 导出本地预览，"
            "或加 --dry-run 仅统计。",
            file=sys.stderr,
        )
        return 2

    if args.start_id and not args.table:
        print("error: --start-id 需与 --table 一起使用", file=sys.stderr)
        return 2

    snapshot_dates = _parse_snapshot_dates(args.snapshot_date)

    if not args.skip_migration:
        if args.dry_run:
            print("running schema migration (required before dry-run)...", flush=True)
        else:
            print("running schema migration...", flush=True)
        run_migration()
        print("migration done", flush=True)

    targets = (args.table,) if args.table else TABLES
    total_scanned = 0
    total_changed = 0
    for table in targets:
        start_id = args.start_id if args.table == table else 0
        if start_id:
            print(f"formatting {table} from id > {start_id}...", flush=True)
        elif snapshot_dates:
            dates_label = ", ".join(
                sorted(
                    ("NULL" if d is None else d.isoformat() for d in snapshot_dates),
                    key=lambda s: (s == "NULL", s),
                )
            )
            print(f"formatting {table} (snapshot_date: {dates_label})...", flush=True)
        elif args.only_list_brand:
            print(f"formatting {table} (only list-brand rows)...", flush=True)
        else:
            print(f"formatting {table}...", flush=True)
        scanned, changed = format_table(
            table,
            dry_run=args.dry_run,
            start_id=start_id,
            snapshot_dates=snapshot_dates,
            only_list_brand=args.only_list_brand,
        )
        total_scanned += scanned
        total_changed += changed
        verb = "would update" if args.dry_run else "updated"
        print(f"{table}: scanned {scanned:,}, {verb} {changed:,}", flush=True)

    print(f"done: {total_changed:,} / {total_scanned:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
