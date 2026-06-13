#!/usr/bin/env python3
"""读取 export_format_preview 导出的 JSONL（含 old_data），按飞书原值格式化并写回库。

流程：先用 backfill_feishu_fields.py 从飞书恢复 → export_format_preview 导出 old_data
→ 本脚本用 old_data 作为颜色/材质合并基准，拆分型号并写库。

  python3 scripts/export_format_preview.py --output-dir data/format_preview/restore
  python3 scripts/backfill_from_old_data.py --input-dir data/format_preview/restore --dry-run
  python3 scripts/backfill_from_old_data.py --input-dir data/format_preview/restore --write-db
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2
from psycopg2.extras import execute_values

from src.config import load_config
from src.db import get_connection
from src.product_format import format_fr_record, format_v_record
from src.product_format_job import run_migration

load_config()

TABLES = ("F", "R", "V")
WRITE_BATCH = 500
MAX_RETRIES = 8
RETRY_BASE_SEC = 3

_FR_FIELDS = ("brand", "model", "condition", "color", "material", "year", "other")
_V_FIELDS = ("brand", "product_name", "material", "condition", "color", "year", "other")


def _is_transient_db_error(exc: BaseException) -> bool:
    if not isinstance(exc, psycopg2.OperationalError):
        return False
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "timeout",
            "timed out",
            "no route to host",
            "connection reset",
            "connection refused",
            "ssl syscall",
            "server closed",
            "could not receive data",
            "could not send data",
            "broken pipe",
            "eof detected",
        )
    )


def _record_from_old_data(table: str, old_data: dict[str, Any]) -> dict[str, Any]:
    if table in {"F", "R"}:
        return {
            "brand": old_data.get("brand"),
            "model": old_data.get("model"),
            "condition": old_data.get("condition"),
            "color": old_data.get("color"),
            "material": old_data.get("material"),
            "year": None,
            "other": None,
        }
    return {
        "brand": old_data.get("brand"),
        "product_name": old_data.get("product_name"),
        "material": old_data.get("material"),
        "condition": old_data.get("condition"),
        "color": old_data.get("color"),
        "year": None,
        "other": None,
    }


def _format_record(table: str, record: dict[str, Any]) -> None:
    if table in {"F", "R"}:
        format_fr_record(record)
    else:
        format_v_record(record)


def _bulk_update_fr(cur, table: str, updates: list[tuple]) -> None:
    if not updates:
        return
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET brand = v.brand,
            model = v.model,
            condition = v.condition,
            color = v.color,
            material = v.material,
            year = v.year,
            other = v.other
        FROM (VALUES %s) AS v(
            id, brand, model, condition, color, material, year, other
        )
        WHERE t.id = v.id
        """,
        updates,
        page_size=WRITE_BATCH,
    )


def _bulk_update_v(cur, updates: list[tuple]) -> None:
    if not updates:
        return
    execute_values(
        cur,
        """
        UPDATE "V" AS t
        SET brand = v.brand,
            product_name = v.product_name,
            material = v.material,
            condition = v.condition,
            color = v.color,
            year = v.year,
            other = v.other
        FROM (VALUES %s) AS v(
            id, brand, product_name, material, condition, color, year, other
        )
        WHERE t.id = v.id
        """,
        updates,
        page_size=WRITE_BATCH,
    )


def _write_batch(table: str, updates: list[tuple]) -> None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = 0")
                    if table in {"F", "R"}:
                        _bulk_update_fr(cur, table, updates)
                    else:
                        _bulk_update_v(cur, updates)
                conn.commit()
            finally:
                conn.close()
            return
        except psycopg2.Error as exc:
            if not _is_transient_db_error(exc) or attempt == MAX_RETRIES:
                raise
            wait = min(RETRY_BASE_SEC * (2 ** (attempt - 1)), 60)
            print(
                f"  {table}: transient DB error, retry {attempt}/{MAX_RETRIES} in {wait}s",
                flush=True,
            )
            time.sleep(wait)


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc


def process_table(
    table: str,
    jsonl_path: Path,
    *,
    dry_run: bool,
    limit: int | None = None,
) -> dict[str, int]:
    if not jsonl_path.is_file():
        print(f"  {table}: 跳过，无文件 {jsonl_path}", flush=True)
        return {"scanned": 0, "changed": 0, "skipped_no_old_data": 0}

    scanned = 0
    changed = 0
    skipped_no_old_data = 0
    pending: list[tuple] = []

    for entry in _iter_jsonl(jsonl_path):
        if limit is not None and scanned >= limit:
            break

        if entry.get("table") not in (None, table):
            continue

        old_data = entry.get("old_data")
        if not old_data:
            skipped_no_old_data += 1
            continue

        row_id = int(entry["id"])
        record = _record_from_old_data(table, old_data)
        before = tuple(record.get(f) for f in (_FR_FIELDS if table in {"F", "R"} else _V_FIELDS))
        _format_record(table, record)
        after = tuple(record.get(f) for f in (_FR_FIELDS if table in {"F", "R"} else _V_FIELDS))

        scanned += 1
        if after != before:
            changed += 1
            pending.append((row_id, *after))

        if not dry_run and len(pending) >= WRITE_BATCH:
            _write_batch(table, pending)
            pending.clear()

        if scanned % 10000 == 0:
            print(f"  {table}: scanned {scanned:,}, changed {changed:,}", flush=True)

    if not dry_run and pending:
        _write_batch(table, pending)

    return {
        "scanned": scanned,
        "changed": changed,
        "skipped_no_old_data": skipped_no_old_data,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="从 JSONL old_data 格式化并写回 F/R/V")
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="export_format_preview 输出目录（含 F.jsonl / R.jsonl / V.jsonl）",
    )
    parser.add_argument("--table", choices=TABLES, help="只处理指定表")
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="写入数据库（默认 dry-run 仅统计）",
    )
    parser.add_argument("--skip-migration", action="store_true", help="跳过 ADD COLUMN 迁移")
    parser.add_argument("--limit", type=int, help="每表最多处理行数（调试用）")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        print(f"error: 目录不存在 {input_dir}", file=sys.stderr)
        return 2

    dry_run = not args.write_db

    if not args.skip_migration and args.write_db:
        print("running schema migration...", flush=True)
        run_migration()
        print("migration done", flush=True)

    targets = (args.table,) if args.table else TABLES
    mode = "dry-run" if dry_run else "write"
    print(f"backfill from old_data ({mode}) ← {input_dir}", flush=True)

    summary: dict[str, Any] = {"input_dir": str(input_dir), "tables": {}}
    for table in targets:
        jsonl_path = input_dir / f"{table}.jsonl"
        print(f"\n=== {table} ===", flush=True)
        stats = process_table(table, jsonl_path, dry_run=dry_run, limit=args.limit)
        summary["tables"][table] = stats
        verb = "would update" if dry_run else "updated"
        print(
            f"{table}: scanned {stats['scanned']:,}, {verb} {stats['changed']:,}, "
            f"skipped (no old_data) {stats['skipped_no_old_data']:,}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
