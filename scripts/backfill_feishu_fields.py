#!/usr/bin/env python3
"""从飞书 xlsx 恢复 F / R / V 被格式化覆盖的商品字段（不删行、不重导其它列）。

用于撤销 format_product_fields 写库后的 brand/model/color/material 等变更，
以飞书原值为准覆盖写回；衍生列 material/year/other（F/R 无飞书材质列）一并清空。

  python3 scripts/backfill_feishu_fields.py --restore --dry-run
  python3 scripts/backfill_feishu_fields.py --restore --category F
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2
from psycopg2.extras import execute_values

from src.config import env_int, feishu_folders, load_config
from src.db import db_session
from src.feishu_client import FeishuClient
from src.snapshot_date import parse_snapshot_date
from src.xlsx_import import iter_sheet_rows

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


def _write_updates(table_kind: str, table: str, updates: list[tuple]) -> int:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with db_session() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = 0")
                    if table_kind in {"F", "R"}:
                        return _update_fr_rows(cur, table, updates)
                    return _update_v_rows(cur, updates)
        except psycopg2.Error as exc:
            if not _is_transient_db_error(exc) or attempt == MAX_RETRIES:
                raise
            wait = min(RETRY_BASE_SEC * (2 ** (attempt - 1)), 60)
            _log(f"    DB 重试 {attempt}/{MAX_RETRIES} in {wait}s ({exc!s:.80})")
            time.sleep(wait)
    raise RuntimeError("unreachable")


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


def _fr_row_to_update(record: dict[str, Any]) -> tuple | None:
    item_id = record.get("item_id")
    if not item_id:
        return None
    return (
        str(item_id).strip(),
        record.get("snapshot_date"),
        record.get("brand"),
        record.get("model"),
        record.get("condition"),
        record.get("color"),
    )


def _v_row_to_update(record: dict[str, Any]) -> tuple | None:
    item_id = record.get("item_id")
    if not item_id:
        return None
    return (
        str(item_id).strip(),
        record.get("snapshot_date"),
        record.get("brand"),
        record.get("product_name"),
        record.get("material"),
        record.get("color"),
        record.get("condition"),
        record.get("size"),
    )


def _update_fr_rows(cur, table: str, rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET brand = v.brand,
            model = v.model,
            condition = v.condition,
            color = v.color,
            material = NULL,
            year = NULL,
            other = NULL
        FROM (VALUES %s) AS v(
            item_id, snapshot_date, brand, model, condition, color
        )
        WHERE t.item_id = v.item_id
          AND t.snapshot_date IS NOT DISTINCT FROM v.snapshot_date::date
        """,
        rows,
        page_size=500,
    )
    return cur.rowcount


def _update_v_rows(cur, rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_values(
        cur,
        """
        UPDATE "V" AS t
        SET brand = v.brand,
            product_name = v.product_name,
            material = v.material,
            color = v.color,
            condition = v.condition,
            size = v.size,
            year = NULL,
            other = NULL
        FROM (VALUES %s) AS v(
            item_id, snapshot_date, brand, product_name, material, color, condition, size
        )
        WHERE t.item_id = v.item_id
          AND t.snapshot_date IS NOT DISTINCT FROM v.snapshot_date::date
        """,
        rows,
        page_size=500,
    )
    return cur.rowcount


def backfill_one_file(
    *,
    item: dict[str, Any],
    table: str,
    table_kind: str,
    dry_run: bool,
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

    convert = _fr_row_to_update if table_kind in {"F", "R"} else _v_row_to_update
    updates: list[tuple] = []
    for record in records:
        row = convert(record)
        if row:
            updates.append(row)

    if not updates:
        _log(f"    无有效行 ({len(records)} 行) [{name}]")
        return len(records), 0, 0

    if dry_run:
        _log(f"    将恢复 {len(updates)} 条 [{name}]")
        return len(records), len(updates), 0

    updated = _write_updates(table_kind, table, updates)

    _log(f"    解析 {len(records)} 行，候选 {len(updates)} 条，更新 {updated} 行 [{name}]")
    return len(records), len(updates), updated


def backfill_folder(
    folder_token: str,
    *,
    table: str,
    table_kind: str,
    workers: int = 1,
    dry_run: bool = False,
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
    parser = argparse.ArgumentParser(description="从飞书 xlsx 恢复被格式化覆盖的商品字段")
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
        "--restore",
        action="store_true",
        help="用飞书原值覆盖库内 brand/model/color 等（必填，防止误触）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计，不写库",
    )
    args = parser.parse_args()

    if not args.restore:
        print("error: 须加 --restore 确认从飞书覆盖写回", file=sys.stderr)
        return 2

    load_config()
    workers = args.workers if args.workers is not None else env_int("IMPORT_WORKERS", 4)
    workers = max(1, workers)

    folders = feishu_folders()
    categories = args.category or ["F", "R", "V"]

    grand_files = 0
    grand_parsed = 0
    grand_candidates = 0
    grand_updated = 0

    mode = "dry-run" if args.dry_run else "write"
    print(f"backfill feishu fields ({mode}, 覆盖全部商品字段)", flush=True)

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
            dry_run=args.dry_run,
        )
        grand_files += files
        grand_parsed += parsed
        grand_candidates += candidates
        grand_updated += updated
        verb = "将更新" if args.dry_run else "已更新"
        print(
            f"{cat}: {files} 个文件，解析 {parsed:,} 行，候选 {candidates:,} 条，{verb} {updated:,} 行",
            flush=True,
        )

    verb = "将更新" if args.dry_run else "已更新"
    print(
        f"\n合计: {grand_files} 个文件，解析 {grand_parsed:,} 行，"
        f"候选 {grand_candidates:,} 条，{verb} {grand_updated:,} 行",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
