#!/usr/bin/env python3
"""从飞书云盘 xlsx 导入三家竞品已售数据到表 F / R / V，不保留飞书元数据。"""

from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from psycopg2.extras import execute_batch

from src.config import env_bool, env_int, feishu_folders, load_config
from src.db import db_session, drop_legacy_tables, init_schema
from src.feishu_client import FeishuClient
from src.image_mirror import mirror_records_batch
from src.r2_storage import R2Storage, r2_settings_from_env
from src.snapshot_date import parse_snapshot_date
from src.xlsx_import import FR_COLUMNS, V_COLUMNS, clear_image_fields, iter_sheet_rows

FOLDER_TO_TABLE = {
    "F": ("F", "F"),
    "R": ("R", "R"),
    "V": ("V", "V"),
}

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def delete_snapshot_date(cur, table: str, snapshot_date: date | None) -> int:
    """按日覆盖：删除该表在指定 snapshot_date 上的全部行（含 NULL）。"""
    if snapshot_date is None:
        cur.execute(f'DELETE FROM "{table}" WHERE snapshot_date IS NULL')
    else:
        cur.execute(
            f'DELETE FROM "{table}" WHERE snapshot_date = %s',
            (snapshot_date,),
        )
    return cur.rowcount


def insert_batch(cur, table: str, columns: list[str], rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})'
    values = [tuple(row.get(c) for c in columns) for row in rows]
    execute_batch(cur, sql, values, page_size=500)
    return len(rows)


def _list_xlsx_items(client: FeishuClient, folder_token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in client.list_files(folder_token):
        name = item.get("name", "")
        if name.lower().endswith((".xlsx", ".xls")):
            items.append(item)
    return items


def load_existing_snapshot_dates(table: str) -> tuple[set[date], bool]:
    """返回 (已有 snapshot_date 集合, 是否存在 snapshot_date IS NULL 的行)。"""
    dates: set[date] = set()
    has_null = False
    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute(f'SELECT DISTINCT snapshot_date FROM "{table}"')
            for (snap,) in cur.fetchall():
                if snap is None:
                    has_null = True
                else:
                    dates.add(snap)
    return dates, has_null


def filter_items_for_import(
    items: list[dict[str, Any]],
    existing_dates: set[date],
    has_null_snapshot: bool,
    *,
    skip_existing: bool,
) -> tuple[list[dict[str, Any]], int]:
    """筛选待导入 xlsx；返回 (待导入列表, 跳过数量)。"""
    scheduled: set[date | None] = set()
    to_import: list[dict[str, Any]] = []
    skipped = 0
    for item in sorted(items, key=lambda i: i.get("name", "")):
        name = item["name"]
        snap = parse_snapshot_date(name)
        if skip_existing:
            if snap is None and has_null_snapshot:
                _log(f"  跳过（库中已有 snapshot_date 为空）: {name}")
                skipped += 1
                continue
            if snap is not None and snap in existing_dates:
                _log(f"  跳过（库中已有 snapshot_date={snap}）: {name}")
                skipped += 1
                continue
        if snap in scheduled:
            _log(f"  跳过（本批已安排同 snapshot_date={snap}）: {name}")
            skipped += 1
            continue
        scheduled.add(snap)
        to_import.append(item)
    return to_import, skipped


def import_one_file(
    *,
    item: dict[str, Any],
    table: str,
    table_kind: str,
    batch_size: int,
    mirror_images: bool,
    empty_images: bool,
    r2_storage: R2Storage | None,
) -> tuple[int, int]:
    """导入单个 xlsx；返回 (是否成功 0/1, 写入行数)。"""
    name = item["name"]
    snapshot = parse_snapshot_date(name)
    _log(f"  下载并解析: {name}")
    if snapshot is None:
        _log("    警告: 文件名未解析出 snapshot_date，将覆盖 snapshot_date 为空的既有行")

    client = FeishuClient()
    content, _ = client.download_file(item["token"], max_bytes=None)
    if content is None:
        _log("    跳过（下载失败）")
        return 0, 0

    columns = FR_COLUMNS if table_kind in {"F", "R"} else V_COLUMNS
    try:
        records = list(
            iter_sheet_rows(content, table_kind=table_kind, snapshot_date=snapshot)
        )
    except BadZipFile:
        _log("    跳过（不是有效的 xlsx 文件，可能下载不完整）")
        return 0, 0
    except Exception as exc:
        _log(f"    跳过（解析失败: {exc}）")
        return 0, 0

    _log(f"    解析 {len(records)} 行 [{name}]")

    if empty_images and not mirror_images:
        for record in records:
            clear_image_fields(record, table_kind)

    if mirror_images and r2_storage is not None:
        _log(f"    镜像图片到 R2 [{name}]...")
        file_stats = mirror_records_batch(
            records,
            table_kind=table_kind,
            storage=r2_storage,
            key_prefix=r2_storage.key_prefix,
            feishu_headers=client.headers,
        )
        _log(
            f"    图片镜像 [{name}]: 新上传 {file_stats.ok}, 失败 {file_stats.failed}"
        )

    file_rows = 0
    with db_session() as conn:
        with conn.cursor() as cur:
            deleted = delete_snapshot_date(cur, table, snapshot)
            if deleted:
                _log(f"    按日覆盖: 已删除 {deleted} 行 (snapshot_date={snapshot}) [{name}]")

            batch: list[dict] = []
            for record in records:
                batch.append(record)
                if len(batch) >= batch_size:
                    file_rows += insert_batch(cur, table, columns, batch)
                    batch.clear()
            if batch:
                file_rows += insert_batch(cur, table, columns, batch)

    _log(f"    写入 {file_rows} 行 (snapshot_date={snapshot}) [{name}]")
    return 1, file_rows


def import_folder(
    folder_token: str,
    *,
    table: str,
    table_kind: str,
    batch_size: int = 500,
    mirror_images: bool = False,
    empty_images: bool = True,
    r2_storage: R2Storage | None = None,
    workers: int = 1,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    list_client = FeishuClient()
    items = _list_xlsx_items(list_client, folder_token)
    if not items:
        return 0, 0, 0

    existing_dates, has_null = load_existing_snapshot_dates(table)
    if skip_existing:
        _log(
            f"  库中已有 {len(existing_dates)} 个 snapshot_date"
            + ("，含 snapshot_date 为空的快照" if has_null else "")
        )
    items, skipped = filter_items_for_import(
        items,
        existing_dates,
        has_null,
        skip_existing=skip_existing,
    )
    if not items:
        _log(f"  无需导入（跳过 {skipped} 个 xlsx）")
        return 0, 0, skipped

    workers = max(1, min(workers, len(items)))
    _log(f"  待导入 {len(items)} 个 xlsx（已跳过 {skipped} 个），并行度 {workers}")

    if workers == 1:
        total_files = 0
        total_rows = 0
        for item in items:
            f, r = import_one_file(
                item=item,
                table=table,
                table_kind=table_kind,
                batch_size=batch_size,
                mirror_images=mirror_images,
                empty_images=empty_images,
                r2_storage=r2_storage,
            )
            total_files += f
            total_rows += r
        return total_files, total_rows, skipped

    total_files = 0
    total_rows = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                import_one_file,
                item=item,
                table=table,
                table_kind=table_kind,
                batch_size=batch_size,
                mirror_images=mirror_images,
                empty_images=empty_images,
                r2_storage=r2_storage,
            )
            for item in items
        ]
        for fut in as_completed(futures):
            f, r = fut.result()
            total_files += f
            total_rows += r

    return total_files, total_rows, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category",
        action="append",
        choices=["F", "R", "V"],
        help="只导入指定目录（可重复）",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DROP 并重建 F/R/V 表（清空全部历史；与默认累积保留相反）",
    )
    parser.add_argument(
        "--drop-legacy",
        action="store_true",
        help="删除旧表 feishu_files（数据量大，较慢）",
    )
    parser.add_argument(
        "--mirror-images",
        action="store_true",
        help="将表格中的图片 URL 下载并上传到 R2，库中写入 R2 公开地址（也可用 R2_MIRROR_IMAGES=true）",
    )
    parser.add_argument(
        "--keep-image-urls",
        action="store_true",
        help="保留 xlsx 中的图片链接入库（默认清空图片列，仅导其它数据）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="并行导入的 xlsx 文件数（默认 IMPORT_WORKERS 或 4）",
    )
    parser.add_argument(
        "--reimport-all",
        action="store_true",
        help="导入飞书目录中的全部 xlsx，并对已有 snapshot_date 按日覆盖（默认仅导入库中尚无的日期）",
    )
    args = parser.parse_args()

    load_config()
    workers = args.workers if args.workers is not None else env_int("IMPORT_WORKERS", 4)
    workers = max(1, workers)

    mirror_images = args.mirror_images or env_bool("R2_MIRROR_IMAGES", False)
    empty_images = not args.keep_image_urls and env_bool("IMPORT_EMPTY_IMAGES", True)
    if mirror_images:
        empty_images = False
    r2_storage: R2Storage | None = None
    if mirror_images:
        r2_storage = R2Storage(r2_settings_from_env())
        print("已启用图片镜像：飞书表格 URL -> R2", flush=True)
    elif empty_images:
        print("图片字段将留空（品牌/价格等照常导入）", flush=True)

    skip_existing = not args.reimport_all
    if skip_existing:
        print(
            "增量导入: 仅处理库中尚无的 snapshot_date（--reimport-all 可强制全量按日覆盖）",
            flush=True,
        )
    else:
        print("全量导入: 处理目录内全部 xlsx，已有 snapshot_date 将按日覆盖", flush=True)
    print(f"并行导入: 每目录最多 {workers} 个 xlsx 同时处理", flush=True)

    if args.drop_legacy:
        print("正在删除 feishu_files / feishu_file_rows ...", flush=True)
        drop_legacy_tables()
        print("旧表已删除。", flush=True)
    if args.reset:
        init_schema()
        print("已重建表 F / R / V。", flush=True)

    should_import = args.reset or args.category is not None or not args.drop_legacy
    if not should_import:
        return 0

    selected = args.category or ["F", "R", "V"]
    folders = feishu_folders()

    for folder_key in selected:
        table, table_kind = FOLDER_TO_TABLE[folder_key]
        token = folders[folder_key]
        mode = "增量（仅新 snapshot_date）" if skip_existing else "全量（按日覆盖）"
        print(
            f'\n==> 导入 {folder_key} -> 表 "{table}"（累积保留，{mode}）',
            flush=True,
        )
        files, rows, skipped = import_folder(
            token,
            table=table,
            table_kind=table_kind,
            mirror_images=mirror_images,
            empty_images=empty_images,
            r2_storage=r2_storage,
            workers=workers,
            skip_existing=skip_existing,
        )
        print(
            f"  完成: 导入 {files} 个文件, {rows} 行, 跳过 {skipped} 个",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
