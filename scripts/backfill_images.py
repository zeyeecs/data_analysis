#!/usr/bin/env python3
"""从飞书 xlsx 仅回填 F / R / V 的图片列（不删行、不重导其它列）。

默认只更新库内尚无可用图片链接的行；可选镜像到 R2（与 import_to_tables --mirror-images 相同）。

  python3 scripts/backfill_images.py --mirror-images --dry-run --category F
  python3 scripts/backfill_images.py --mirror-images --category F --workers 2
  python3 scripts/backfill_images.py --keep-image-urls --category F   # 直接写入 xlsx 中的飞书 URL
"""

from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from psycopg2.extras import execute_values

from src.config import env_bool, env_int, feishu_folders, load_config
from src.db import db_session
from src.feishu_client import FeishuClient
from src.image_mirror import extract_urls, mirror_records_batch
from src.r2_storage import R2Storage, r2_settings_from_env
from src.snapshot_date import parse_snapshot_date
from src.xlsx_import import iter_sheet_rows

FOLDER_TO_TABLE = {
    "F": ("F", "F"),
    "R": ("R", "R"),
    "V": ("V", "V"),
}

_print_lock = threading.Lock()


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


def _record_has_image_source(record: dict[str, Any], table_kind: str) -> bool:
    if table_kind in {"F", "R"}:
        for field in ("image_path", "image_urls"):
            text = record.get(field)
            if text and extract_urls(str(text)):
                return True
        return False
    text = record.get("image")
    return bool(text and extract_urls(str(text)))


def _missing_image_sql(table_kind: str) -> str:
    if table_kind in {"F", "R"}:
        return """
            COALESCE(btrim(image_urls), '') = ''
            AND COALESCE(btrim(image_path), '') = ''
        """
    return "COALESCE(btrim(image), '') = ''"


def load_snapshot_dates_missing_images(
    table: str,
    table_kind: str,
    *,
    from_snapshot_date: date | None = None,
) -> dict[date | None, int]:
    """返回库内仍有缺图行的 snapshot_date -> 缺图行数。"""
    missing = _missing_image_sql(table_kind)
    params: list[object] = []
    date_filter = ""
    if from_snapshot_date is not None:
        date_filter = " AND snapshot_date >= %s"
        params.append(from_snapshot_date)

    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT snapshot_date, COUNT(*) AS missing_rows
                FROM "{table}"
                WHERE {missing}
                {date_filter}
                GROUP BY snapshot_date
                ORDER BY snapshot_date
                """,
                params,
            )
            return {row[0]: int(row[1]) for row in cur.fetchall()}


def filter_items_for_image_backfill(
    items: list[dict[str, Any]],
    missing_by_date: dict[date | None, int],
    *,
    from_snapshot_date: date | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """只保留库内仍缺图的 snapshot_date 对应 xlsx。"""
    if not missing_by_date:
        return [], len(items)

    selected: list[dict[str, Any]] = []
    skipped = 0
    for item in items:
        snap = parse_snapshot_date(item.get("name", ""))
        if snap is None or snap not in missing_by_date:
            skipped += 1
            continue
        if from_snapshot_date is not None and snap is not None and snap < from_snapshot_date:
            skipped += 1
            continue
        selected.append(item)
    return selected, skipped


def _empty_image_clause(table_kind: str) -> str:
    if table_kind in {"F", "R"}:
        return """
          AND COALESCE(btrim(t.image_urls), '') = ''
          AND COALESCE(btrim(t.image_path), '') = ''
        """
    return " AND COALESCE(btrim(t.image), '') = ''"


def _update_images_fr(
    cur,
    table: str,
    rows: list[tuple[str | None, date | None, str | None, str | None]],
    *,
    only_empty: bool,
) -> int:
    if not rows:
        return 0
    null_clause = _empty_image_clause("F") if only_empty else ""
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET image_path = v.image_path,
            image_urls = v.image_urls
        FROM (VALUES %s) AS v(item_id, snapshot_date, image_path, image_urls)
        WHERE t.item_id = v.item_id
          AND t.snapshot_date IS NOT DISTINCT FROM v.snapshot_date::date
          {null_clause}
        """,
        rows,
        page_size=500,
    )
    return cur.rowcount


def _update_images_v(
    cur,
    table: str,
    rows: list[tuple[str | None, date | None, str | None]],
    *,
    only_empty: bool,
) -> int:
    if not rows:
        return 0
    null_clause = _empty_image_clause("V") if only_empty else ""
    execute_values(
        cur,
        f"""
        UPDATE "{table}" AS t
        SET image = v.image
        FROM (VALUES %s) AS v(item_id, snapshot_date, image)
        WHERE t.item_id = v.item_id
          AND t.snapshot_date IS NOT DISTINCT FROM v.snapshot_date::date
          {null_clause}
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
    only_empty: bool,
    dry_run: bool,
    mirror_images: bool,
    r2_storage: R2Storage | None,
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
        records = list(iter_sheet_rows(content, table_kind=table_kind, snapshot_date=snapshot))
    except BadZipFile:
        _log("    跳过（不是有效的 xlsx 文件）")
        return 0, 0, 0
    except Exception as exc:
        _log(f"    跳过（解析失败: {exc}）")
        return 0, 0, 0

    candidates: list[dict[str, Any]] = []
    for record in records:
        if not record.get("item_id"):
            continue
        if not _record_has_image_source(record, table_kind):
            continue
        candidates.append(record)

    if not candidates:
        _log(f"    无有效图片 ({len(records)} 行) [{name}]")
        return len(records), 0, 0

    if dry_run:
        _log(f"    将回填 {len(candidates)} 条图片（dry-run 不镜像、不写库） [{name}]")
        return len(records), len(candidates), 0

    if mirror_images and r2_storage is not None:
        _log(f"    镜像图片到 R2 [{name}]...")
        stats = mirror_records_batch(
            candidates,
            table_kind=table_kind,
            storage=r2_storage,
            key_prefix=r2_storage.key_prefix,
            feishu_headers=client.headers,
        )
        _log(f"    图片镜像 [{name}]: 新上传 {stats.ok}, 失败 {stats.failed}")

    if table_kind in {"F", "R"}:
        updates_fr: list[tuple[str | None, date | None, str | None, str | None]] = []
        for record in candidates:
            updates_fr.append(
                (
                    str(record["item_id"]).strip(),
                    record.get("snapshot_date"),
                    record.get("image_path"),
                    record.get("image_urls"),
                )
            )
        update_rows = updates_fr
    else:
        updates_v: list[tuple[str | None, date | None, str | None]] = []
        for record in candidates:
            updates_v.append(
                (
                    str(record["item_id"]).strip(),
                    record.get("snapshot_date"),
                    record.get("image"),
                )
            )
        update_rows = updates_v

    updated = 0
    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            if table_kind in {"F", "R"}:
                updated = _update_images_fr(
                    cur, table, update_rows, only_empty=only_empty
                )
            else:
                updated = _update_images_v(cur, table, update_rows, only_empty=only_empty)

    _log(f"    解析 {len(records)} 行，候选 {len(update_rows)} 条，更新 {updated} 行 [{name}]")
    return len(records), len(update_rows), updated


def backfill_folder(
    folder_token: str,
    *,
    table: str,
    table_kind: str,
    workers: int = 1,
    only_empty: bool = True,
    dry_run: bool = False,
    mirror_images: bool = False,
    r2_storage: R2Storage | None = None,
    only_db_missing: bool = False,
    from_snapshot_date: date | None = None,
) -> tuple[int, int, int, int]:
    client = FeishuClient()
    items = sorted(_list_xlsx_items(client, folder_token), key=lambda i: i.get("name", ""))
    if not items:
        return 0, 0, 0, 0

    if only_db_missing:
        missing_by_date = load_snapshot_dates_missing_images(
            table,
            table_kind,
            from_snapshot_date=from_snapshot_date,
        )
        if not missing_by_date:
            _log("  库内无缺图 snapshot_date，跳过")
            return 0, 0, 0, 0
        dates_label = ", ".join(
            d.isoformat() if d is not None else "NULL"
            for d in sorted(missing_by_date, key=lambda x: (x is None, x))
        )
        _log(
            f"  库内缺图 snapshot_date ({len(missing_by_date)} 个): {dates_label}"
        )
        items, skipped = filter_items_for_image_backfill(
            items,
            missing_by_date,
            from_snapshot_date=from_snapshot_date,
        )
        _log(f"  匹配飞书 xlsx {len(items)} 个（跳过 {skipped} 个）")
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
            only_empty=only_empty,
            dry_run=dry_run,
            mirror_images=mirror_images,
            r2_storage=r2_storage,
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
    parser = argparse.ArgumentParser(description="从飞书 xlsx 仅回填图片列")
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
        "--all-rows",
        action="store_true",
        help="覆盖库中已有图片 URL（默认仅填空图片列）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计，不写库",
    )
    parser.add_argument(
        "--mirror-images",
        action="store_true",
        help="将 xlsx 中的图片 URL 镜像到 R2 后写入（也可用 R2_MIRROR_IMAGES=true）",
    )
    parser.add_argument(
        "--keep-image-urls",
        action="store_true",
        help="直接写入 xlsx 中的飞书链接（不镜像；与 --mirror-images 二选一）",
    )
    parser.add_argument(
        "--only-db-missing",
        action="store_true",
        help="仅处理库内仍有缺图行的 snapshot_date 对应 xlsx（推荐）",
    )
    parser.add_argument(
        "--from-snapshot-date",
        type=str,
        metavar="YYYY-MM-DD",
        help="只处理该日期及之后的缺图 snapshot（配合 --only-db-missing）",
    )
    parser.add_argument(
        "--report-missing",
        action="store_true",
        help="只打印库内缺图 snapshot 统计，不下载飞书文件",
    )
    args = parser.parse_args()

    load_config()
    workers = args.workers if args.workers is not None else env_int("IMPORT_WORKERS", 4)
    workers = max(1, workers)
    only_empty = not args.all_rows

    from_snapshot_date: date | None = None
    if args.from_snapshot_date:
        from_snapshot_date = date.fromisoformat(args.from_snapshot_date)

    if args.report_missing:
        folders = feishu_folders()
        categories = args.category or ["F", "R", "V"]
        for cat in categories:
            table, table_kind = FOLDER_TO_TABLE[cat]
            missing = load_snapshot_dates_missing_images(
                table,
                table_kind,
                from_snapshot_date=from_snapshot_date,
            )
            total_missing_rows = sum(missing.values())
            print(f"\n== {cat} 缺图 snapshot ({len(missing)} 个, 共 {total_missing_rows:,} 行)")
            if not missing:
                print("  （无）")
                continue
            for snap, rows in missing.items():
                label = snap.isoformat() if snap is not None else "NULL"
                print(f"  {label}\t{rows:,} 行")
        return 0

    mirror_images = args.mirror_images or env_bool("R2_MIRROR_IMAGES", False)
    keep_urls = args.keep_image_urls
    if mirror_images and keep_urls:
        print("请只指定 --mirror-images 或 --keep-image-urls 之一", file=sys.stderr)
        return 2
    if not mirror_images and not keep_urls:
        print(
            "请指定 --mirror-images（推荐，写入 R2 公开地址）或 --keep-image-urls（写入飞书原链）",
            file=sys.stderr,
        )
        return 2

    r2_storage: R2Storage | None = None
    if mirror_images:
        r2_storage = R2Storage(r2_settings_from_env())

    folders = feishu_folders()
    categories = args.category or ["F", "R", "V"]

    grand_files = 0
    grand_parsed = 0
    grand_candidates = 0
    grand_updated = 0

    mode = "dry-run" if args.dry_run else "write"
    scope = "仅空图片" if only_empty else "覆盖全部图片"
    img_mode = "镜像 R2" if mirror_images else "保留飞书 URL"
    print(f"backfill images ({mode}, {scope}, {img_mode})", flush=True)

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
            only_empty=only_empty,
            dry_run=args.dry_run,
            mirror_images=mirror_images,
            r2_storage=r2_storage,
            only_db_missing=args.only_db_missing,
            from_snapshot_date=from_snapshot_date,
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
