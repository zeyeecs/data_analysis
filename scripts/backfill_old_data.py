#!/usr/bin/env python3
"""从飞书 xlsx 回填 F/R/V 的 old_data 列（飞书原值 JSON 快照，不改其它列）。

  python3 scripts/backfill_old_data.py --dry-run
  python3 scripts/backfill_old_data.py --write-db
  python3 scripts/backfill_old_data.py --write-db --category R --workers 2
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2
from psycopg2.extras import Json, execute_values

from src.config import env_int, feishu_folders, load_config
from src.db import db_session
from src.feishu_client import FeishuClient
from src.product_format_job import run_migration
from src.snapshot_date import parse_snapshot_date
from src.xlsx_import import build_old_data, iter_sheet_rows

FOLDER_TO_TABLE = {
    "F": ("F", "F"),
    "R": ("R", "R"),
    "V": ("V", "V"),
}

_print_lock = threading.Lock()
MAX_RETRIES = 8
RETRY_BASE_SEC = 3


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
            "could not translate host name",
        )
    )


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def _list_xlsx_items(client: FeishuClient, folder_token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in client.list_files(folder_token):
        name = item.get("name", "")
        if name.lower().endswith((".xlsx", ".xls")):
            items.append(item)
    return items


def _row_to_update(record: dict[str, Any], *, table_kind: str) -> tuple | None:
    item_id = record.get("item_id")
    if not item_id:
        return None
    old_data = build_old_data(record, table_kind)
    if not old_data:
        return None
    return (str(item_id).strip(), record.get("snapshot_date"), Json(old_data))


def _update_rows(cur, table: str, rows: list[tuple], *, only_missing: bool) -> int:
    if not rows:
        return 0
    missing_clause = " AND t.old_data IS NULL" if only_missing else ""
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET old_data = v.old_data::jsonb
        FROM (VALUES %s) AS v(item_id, snapshot_date, old_data)
        WHERE t.item_id = v.item_id
          AND t.snapshot_date IS NOT DISTINCT FROM v.snapshot_date::date
          {missing_clause}
        """,
        rows,
        page_size=500,
    )
    return cur.rowcount


def _write_updates(table: str, updates: list[tuple], *, only_missing: bool) -> int:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with db_session() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = 0")
                    return _update_rows(cur, table, updates, only_missing=only_missing)
        except psycopg2.Error as exc:
            if not _is_transient_db_error(exc) or attempt == MAX_RETRIES:
                raise
            wait = min(RETRY_BASE_SEC * (2 ** (attempt - 1)), 60)
            _log(f"    DB 重试 {attempt}/{MAX_RETRIES} in {wait}s ({exc!s:.80})")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def backfill_one_file(
    *,
    item: dict[str, Any],
    table: str,
    table_kind: str,
    dry_run: bool,
    only_missing: bool,
) -> tuple[int, int, int]:
    """返回 (parsed, candidates, updated)。"""
    name = item["name"]
    snapshot = parse_snapshot_date(name)
    _log(f"  下载并解析: {name}")

    client = FeishuClient()
    try:
        content, _ = client.download_file(item["token"], max_bytes=None)
    except requests.RequestException as exc:
        _log(f"    跳过（下载失败: {exc}） [{name}]")
        return 0, 0, 0
    if content is None:
        _log(f"    跳过（下载失败） [{name}]")
        return 0, 0, 0

    try:
        records = list(
            iter_sheet_rows(
                content,
                table_kind=table_kind,
                snapshot_date=snapshot,
                skip_format=True,
            )
        )
    except BadZipFile:
        _log("    跳过（不是有效的 xlsx 文件）")
        return 0, 0, 0
    except Exception as exc:
        _log(f"    跳过（解析失败: {exc}）")
        return 0, 0, 0

    updates: list[tuple] = []
    for record in records:
        row = _row_to_update(record, table_kind=table_kind)
        if row:
            updates.append(row)

    if not updates:
        _log(f"    无有效行 ({len(records)} 行) [{name}]")
        return len(records), 0, 0

    if dry_run:
        _log(f"    将回填 old_data {len(updates)} 条 [{name}]")
        return len(records), len(updates), 0

    updated = _write_updates(table, updates, only_missing=only_missing)
    _log(f"    解析 {len(records)} 行，候选 {len(updates)} 条，更新 {updated} 行 [{name}]")
    return len(records), len(updates), updated


def backfill_folder(
    folder_token: str,
    *,
    table: str,
    table_kind: str,
    workers: int = 1,
    dry_run: bool = False,
    only_missing: bool = True,
) -> tuple[int, int, int, int]:
    client = FeishuClient()
    items = sorted(_list_xlsx_items(client, folder_token), key=lambda i: i.get("name", ""))
    if not items:
        return 0, 0, 0, 0

    workers = max(1, min(workers, len(items)))
    _log(f"  待处理 {len(items)} 个 xlsx，并行度 {workers}")

    total_parsed = 0
    total_candidates = 0
    total_updated = 0
    total_files = 0

    def _run(item: dict[str, Any]) -> tuple[int, int, int]:
        return backfill_one_file(
            item=item,
            table=table,
            table_kind=table_kind,
            dry_run=dry_run,
            only_missing=only_missing,
        )

    if workers == 1:
        for item in items:
            parsed, candidates, updated = _run(item)
            total_parsed += parsed
            total_candidates += candidates
            total_updated += updated
            if parsed > 0:
                total_files += 1
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run, item) for item in items]
            for fut in as_completed(futures):
                try:
                    parsed, candidates, updated = fut.result()
                except Exception as exc:
                    _log(f"    跳过（处理失败: {exc}）")
                    continue
                total_parsed += parsed
                total_candidates += candidates
                total_updated += updated
                if parsed > 0:
                    total_files += 1

    return total_files, total_parsed, total_candidates, total_updated


def main() -> int:
    parser = argparse.ArgumentParser(description="从飞书 xlsx 回填 old_data JSON 快照")
    parser.add_argument(
        "--category",
        action="append",
        choices=["F", "R", "V"],
        help="只处理指定目录（可重复；默认 F/R/V 全部）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="并行 xlsx 数（默认 IMPORT_WORKERS 或 4）",
    )
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="写入数据库（默认 dry-run 仅统计）",
    )
    parser.add_argument(
        "--all-rows",
        action="store_true",
        help="覆盖已有 old_data（默认仅填空值）",
    )
    parser.add_argument(
        "--skip-migration",
        action="store_true",
        help="跳过 ADD COLUMN 迁移",
    )
    args = parser.parse_args()

    load_config()
    dry_run = not args.write_db
    only_missing = not args.all_rows
    workers = args.workers if args.workers is not None else env_int("IMPORT_WORKERS", 4)
    workers = max(1, workers)

    if args.write_db and not args.skip_migration:
        print("running schema migration...", flush=True)
        run_migration()
        print("migration done", flush=True)

    folders = feishu_folders()
    categories = args.category or ["F", "R", "V"]

    grand_files = 0
    grand_parsed = 0
    grand_candidates = 0
    grand_updated = 0

    mode = "dry-run" if dry_run else "write"
    scope = "仅 old_data 为空" if only_missing else "全部行"
    print(f"backfill old_data ({mode}, {scope})", flush=True)

    for cat in categories:
        folder_key, table_kind = FOLDER_TO_TABLE[cat]
        token = folders.get(folder_key)
        if not token:
            print(f"跳过 {cat}: 未配置飞书目录", flush=True)
            continue

        print(f"\n=== {cat} ===", flush=True)
        files, parsed, candidates, updated = backfill_folder(
            token,
            table=table_kind,
            table_kind=table_kind,
            workers=workers,
            dry_run=dry_run,
            only_missing=only_missing,
        )
        grand_files += files
        grand_parsed += parsed
        grand_candidates += candidates
        grand_updated += updated
        verb = "将更新" if dry_run else "已更新"
        print(
            f"{cat}: {files} 个文件，解析 {parsed:,} 行，候选 {candidates:,} 条，{verb} {updated:,} 行",
            flush=True,
        )

    verb = "将更新" if dry_run else "已更新"
    print(
        f"\n合计: {grand_files} 个文件，解析 {grand_parsed:,} 行，"
        f"候选 {grand_candidates:,} 条，{verb} {grand_updated:,} 行",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
