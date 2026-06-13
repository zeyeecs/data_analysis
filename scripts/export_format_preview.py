#!/usr/bin/env python3
"""从 F/R/V 只读解析商品字段，结果写入本地文件，不修改数据库。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2

from src.config import load_config
from src.db import get_connection
from src.product_format import format_fr_record, format_v_record

load_config()

TABLES = ("F", "R", "V")
READ_BATCH = 2000
MAX_RETRIES = 8
RETRY_BASE_SEC = 3

_FR_READ_FIELDS = ("brand", "model", "condition", "color", "material", "year", "other")
_V_READ_FIELDS = ("brand", "product_name", "material", "condition", "color", "year", "other")

_FR_OLD_DATA_FIELDS = (
    "item_id",
    "brand",
    "model",
    "condition",
    "price",
    "color",
    "material",
    "year",
    "other",
    "snapshot_date",
)
_V_OLD_DATA_FIELDS = (
    "item_id",
    "brand",
    "product_name",
    "material",
    "color",
    "year",
    "size",
    "price",
    "currency",
    "seller_price",
    "buyer_fee",
    "likes",
    "listed_at",
    "sold_at",
    "condition",
    "url",
    "other",
    "snapshot_date",
)


def _table_columns(table: str) -> set[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table,),
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def _old_data_columns(table: str, available: set[str]) -> list[str]:
    fields = _FR_OLD_DATA_FIELDS if table in {"F", "R"} else _V_OLD_DATA_FIELDS
    return [field for field in fields if field in available]


def _read_columns(table: str, available: set[str]) -> list[str]:
    fields = _FR_READ_FIELDS if table in {"F", "R"} else _V_READ_FIELDS
    old_data_fields = _old_data_columns(table, available)
    columns = ["id"]
    seen = {"id"}
    for field in (*fields, *old_data_fields):
        if field in available and field not in seen:
            columns.append(field)
            seen.add(field)
    return columns


def _build_old_data(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {col: _serialize(row.get(col)) for col in columns}


def _row_dict(columns: list[str], row: tuple) -> dict[str, Any]:
    return dict(zip(columns, row))


def _record_snapshot(
    table: str,
    row: dict[str, Any],
    *,
    old_data_columns: list[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """返回 (before, after, old_data) 字段 dict；after 为格式化结果。"""
    row_id = int(row["id"])
    old_data = _build_old_data(row, old_data_columns)
    if table in {"F", "R"}:
        before = {"id": row_id, **{f: row.get(f) for f in _FR_READ_FIELDS}}
        record = {f: before[f] for f in _FR_READ_FIELDS}
        format_fr_record(record)
        after = {**before, **record}
    else:
        before = {"id": row_id, **{f: row.get(f) for f in _V_READ_FIELDS}}
        record = {f: before[f] for f in _V_READ_FIELDS}
        format_v_record(record)
        after = {**before, **record}

    for key in before:
        before[key] = _serialize(before[key])
    for key in after:
        after[key] = _serialize(after[key])
    return before, after, old_data


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


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _compare_fields(table: str, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = _FR_READ_FIELDS if table in {"F", "R"} else _V_READ_FIELDS
    return [k for k in keys if before.get(k) != after.get(k)]


def _select_sql(table: str, columns: list[str]) -> str:
    cols = ", ".join(f'"{c}"' if c == "condition" else c for c in columns)
    return f"""
        SELECT {cols}
        FROM "{table}"
        WHERE id > %s
        ORDER BY id
        LIMIT %s
    """


def _csv_headers(table: str) -> list[str]:
    if table in {"F", "R"}:
        return [
            "id",
            "brand_before",
            "brand_after",
            "model_before",
            "model_after",
            "material_before",
            "material_after",
            "color_before",
            "color_after",
            "condition_before",
            "condition_after",
            "year_before",
            "year_after",
            "other_before",
            "other_after",
            "changed_fields",
        ]
    return [
        "id",
        "brand_before",
        "brand_after",
        "product_name_before",
        "product_name_after",
        "material_before",
        "material_after",
        "color_before",
        "color_after",
        "condition_before",
        "condition_after",
        "year_before",
        "year_after",
        "other_before",
        "other_after",
        "changed_fields",
    ]


def _csv_row(table: str, before: dict[str, Any], after: dict[str, Any], changed_fields: list[str]) -> dict[str, Any]:
    joined = "|".join(changed_fields)
    if table in {"F", "R"}:
        return {
            "id": before["id"],
            "brand_before": before.get("brand"),
            "brand_after": after.get("brand"),
            "model_before": before.get("model"),
            "model_after": after.get("model"),
            "material_before": before.get("material"),
            "material_after": after.get("material"),
            "color_before": before.get("color"),
            "color_after": after.get("color"),
            "condition_before": before.get("condition"),
            "condition_after": after.get("condition"),
            "year_before": before.get("year"),
            "year_after": after.get("year"),
            "other_before": before.get("other"),
            "other_after": after.get("other"),
            "changed_fields": joined,
        }
    return {
        "id": before["id"],
        "brand_before": before.get("brand"),
        "brand_after": after.get("brand"),
        "product_name_before": before.get("product_name"),
        "product_name_after": after.get("product_name"),
        "material_before": before.get("material"),
        "material_after": after.get("material"),
        "color_before": before.get("color"),
        "color_after": after.get("color"),
        "condition_before": before.get("condition"),
        "condition_after": after.get("condition"),
        "year_before": before.get("year"),
        "year_after": after.get("year"),
        "other_before": before.get("other"),
        "other_after": after.get("other"),
        "changed_fields": joined,
    }


def _export_table(
    table: str,
    out_dir: Path,
    *,
    start_id: int = 0,
    limit: int | None = None,
    changed_only: bool = False,
) -> dict[str, int]:
    available = _table_columns(table)
    read_columns = _read_columns(table, available)
    old_data_columns = _old_data_columns(table, available)
    missing = [
        f
        for f in (_FR_READ_FIELDS if table in {"F", "R"} else _V_READ_FIELDS)
        if f not in available
    ]
    if missing:
        print(f"  {table}: 库中无列 {', '.join(missing)}，跳过读取；解析结果仍写入 after", flush=True)

    select_sql = _select_sql(table, read_columns)
    jsonl_path = out_dir / f"{table}.jsonl"
    changed_jsonl_path = out_dir / f"{table}_changed.jsonl"
    changed_csv_path = out_dir / f"{table}_changed.csv"

    scanned = 0
    changed = 0
    last_id = start_id
    append = start_id > 0
    prior_scanned = 0
    prior_changed = 0
    if append and jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            prior_scanned = sum(1 for _ in f)
    if append and changed_jsonl_path.exists():
        with changed_jsonl_path.open(encoding="utf-8") as f:
            prior_changed = sum(1 for _ in f)

    with (
        jsonl_path.open("a" if append else "w", encoding="utf-8") as jsonl_f,
        changed_jsonl_path.open("a" if append else "w", encoding="utf-8") as changed_jsonl_f,
        changed_csv_path.open("a" if append else "w", encoding="utf-8", newline="") as csv_f,
    ):
        writer = csv.DictWriter(csv_f, fieldnames=_csv_headers(table))
        if not append:
            writer.writeheader()

        while True:
            batch_limit = READ_BATCH
            if limit is not None:
                remaining = limit - scanned
                if remaining <= 0:
                    break
                batch_limit = min(batch_limit, remaining)

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            cur.execute("SET statement_timeout = 0")
                            cur.execute(select_sql, (last_id, batch_limit))
                            rows = [_row_dict(read_columns, row) for row in cur.fetchall()]
                    finally:
                        conn.close()
                    break
                except psycopg2.Error as exc:
                    if not _is_transient_db_error(exc) or attempt == MAX_RETRIES:
                        raise
                    wait = min(RETRY_BASE_SEC * (2 ** (attempt - 1)), 60)
                    print(
                        f"  {table}: transient DB error ({exc!s:.80}), "
                        f"retry {attempt}/{MAX_RETRIES} in {wait}s (resume id>{last_id})",
                        flush=True,
                    )
                    time.sleep(wait)
            else:
                raise RuntimeError("unreachable")

            if not rows:
                break

            last_id = int(rows[-1]["id"])

            for row in rows:
                before, after, old_data = _record_snapshot(
                    table,
                    row,
                    old_data_columns=old_data_columns,
                )
                changed_fields = _compare_fields(table, before, after)
                is_changed = bool(changed_fields)
                entry = {
                    "table": table,
                    "id": before["id"],
                    "old_data": old_data,
                    "before": before,
                    "after": after,
                    "changed_fields": changed_fields,
                    "changed": is_changed,
                }

                if not changed_only or is_changed:
                    jsonl_f.write(json.dumps(entry, ensure_ascii=False) + "\n")

                if is_changed:
                    changed += 1
                    changed_jsonl_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    writer.writerow(_csv_row(table, before, after, changed_fields))

            scanned += len(rows)
            total_scanned = prior_scanned + scanned
            total_changed = prior_changed + changed
            if scanned % 1000 < READ_BATCH or len(rows) < batch_limit:
                print(
                    f"  {table}: scanned {total_scanned:,}, changed {total_changed:,}, last_id={last_id}",
                    flush=True,
                )

            if len(rows) < batch_limit:
                break

    return {"scanned": prior_scanned + scanned, "changed": prior_changed + changed}


def _default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "data" / "format_preview" / stamp


def main() -> int:
    parser = argparse.ArgumentParser(
        description="只读解析 F/R/V 商品字段，写入本地 JSONL/CSV，不修改数据库"
    )
    parser.add_argument("--table", choices=TABLES, help="只处理指定表；默认三张表都导出")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="输出目录（默认 data/format_preview/<UTC时间戳>/）",
    )
    parser.add_argument("--start-id", type=int, default=0, help="从指定 id 之后继续")
    parser.add_argument("--limit", type=int, help="最多处理行数（调试用）")
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="主 JSONL 也只写入有变更的行（默认写入全部行）",
    )
    args = parser.parse_args()

    if args.start_id and not args.table:
        print("error: --start-id 需与 --table 一起使用", file=sys.stderr)
        return 2

    out_dir = (args.output_dir or _default_output_dir()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = (args.table,) if args.table else TABLES
    summary: dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "tables": {},
        "note": "只读导出，未修改远程数据库",
    }

    print(f"exporting to {out_dir} (read-only, no DB writes)", flush=True)
    for table in targets:
        start_id = args.start_id if args.table == table else 0
        if start_id:
            print(f"exporting {table} from id > {start_id}...", flush=True)
        else:
            print(f"exporting {table}...", flush=True)
        stats = _export_table(
            table,
            out_dir,
            start_id=start_id,
            limit=args.limit,
            changed_only=args.changed_only,
        )
        summary["tables"][table] = stats
        print(
            f"{table}: scanned {stats['scanned']:,}, changed {stats['changed']:,}",
            flush=True,
        )

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"done → {out_dir}", flush=True)
    print(f"  review: {out_dir / (args.table or 'V')}_changed.csv", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
