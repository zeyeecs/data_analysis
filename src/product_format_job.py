"""批量格式化 F / R / V 商品字段（规则引擎 + 可选 LLM 语义解析）。"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extras import execute_values

from src.db import db_session, get_connection
from src.model_semantics import semantic_parse_cache_stats
from src.product_format import format_fr_record, format_record_from_old_data, format_v_record

ROOT = Path(__file__).resolve().parent.parent

TABLES = ("F", "R", "V")
READ_BATCH = 2000
WRITE_BATCH = 500
MAX_RETRIES = 8
RETRY_BASE_SEC = 3


def run_migration() -> None:
    sql_path = ROOT / "sql" / "add_product_format_columns.sql"
    statements = [s.strip() for s in sql_path.read_text(encoding="utf-8").split(";") if s.strip()]
    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            for stmt in statements:
                cur.execute(stmt)


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


def _list_brand_filter_clause(only_list_brand: bool) -> str:
    """竞品 R 等表 brand 常为 Python 列表字面量 ['Hermes']，需归一化。"""
    if not only_list_brand:
        return ""
    return " AND brand LIKE '[%'"


def _snapshot_filter_clause(
    snapshot_dates: Iterable[date | None] | None,
) -> tuple[str, list[date | None]]:
    if snapshot_dates is None:
        return "", []
    unique = set(snapshot_dates)
    if not unique:
        return "", []

    parts: list[str] = []
    params: list[date | None] = []
    concrete = sorted(d for d in unique if d is not None)
    if concrete:
        placeholders = ", ".join(["%s"] * len(concrete))
        parts.append(f"snapshot_date IN ({placeholders})")
        params.extend(concrete)
    if None in unique:
        parts.append("snapshot_date IS NULL")

    if len(parts) == 1:
        return f" AND {parts[0]}", params
    return f" AND ({' OR '.join(parts)})", params


def _process_batch(
    table: str,
    *,
    last_id: int,
    dry_run: bool,
    snapshot_dates: Iterable[date | None] | None = None,
    only_list_brand: bool = False,
) -> tuple[list, int, list[tuple], int]:
    """读一批、格式化；返回 (rows, new_last_id, updates, changed_in_batch)。"""
    snap_clause, snap_params = _snapshot_filter_clause(snapshot_dates)
    list_brand_clause = _list_brand_filter_clause(only_list_brand)
    if table in {"F", "R"}:
        select_sql = f"""
            SELECT id, brand, model, condition, color, material, year, other, old_data
            FROM "{table}"
            WHERE id > %s{snap_clause}{list_brand_clause}
            ORDER BY id
            LIMIT %s
        """
    else:
        select_sql = f"""
            SELECT id, brand, product_name, material, condition, color, year, other, old_data
            FROM "V"
            WHERE id > %s{snap_clause}{list_brand_clause}
            ORDER BY id
            LIMIT %s
        """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(select_sql, (last_id, *snap_params, READ_BATCH))
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return rows, last_id, [], 0

    new_last_id = int(rows[-1][0])
    updates: list[tuple] = []
    changed_in_batch = 0

    for row in rows:
        if table in {"F", "R"}:
            row_id, brand, model, condition, color, material, year, other, old_data = row
            record = {
                "brand": brand,
                "model": model,
                "condition": condition,
                "color": color,
                "material": material,
                "year": year,
                "other": other,
            }
            if isinstance(old_data, dict) and old_data.get("model"):
                format_record_from_old_data(record, old_data, table_kind=table)
            else:
                format_fr_record(record)
            new_row = (
                record["brand"],
                record["model"],
                record["condition"],
                record["color"],
                record["material"],
                record["year"],
                record.get("other"),
            )
            old_row = (brand, model, condition, color, material, year, other)
        else:
            row_id, brand, product_name, material, condition, color, year, other, old_data = row
            record = {
                "brand": brand,
                "product_name": product_name,
                "material": material,
                "condition": condition,
                "color": color,
                "year": year,
                "other": other,
            }
            if isinstance(old_data, dict) and old_data.get("product_name"):
                format_record_from_old_data(record, old_data, table_kind="V")
            else:
                format_v_record(record)
            new_row = (
                record["brand"],
                record["product_name"],
                record["material"],
                record["condition"],
                record["color"],
                record["year"],
                record.get("other"),
            )
            old_row = (brand, product_name, material, condition, color, year, other)

        if new_row != old_row:
            changed_in_batch += 1
            updates.append((int(row_id), *new_row))

    if not dry_run and updates:
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

    return rows, new_last_id, updates, changed_in_batch


def format_table(
    table: str,
    *,
    dry_run: bool,
    start_id: int = 0,
    snapshot_dates: Iterable[date | None] | None = None,
    only_list_brand: bool = False,
    log: bool = True,
) -> tuple[int, int]:
    scanned = 0
    changed = 0
    last_id = start_id

    while True:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                rows, last_id, _updates, batch_changed = _process_batch(
                    table,
                    last_id=last_id,
                    dry_run=dry_run,
                    snapshot_dates=snapshot_dates,
                    only_list_brand=only_list_brand,
                )
                break
            except psycopg2.Error as exc:
                if not _is_transient_db_error(exc) or attempt == MAX_RETRIES:
                    raise
                wait = min(RETRY_BASE_SEC * (2 ** (attempt - 1)), 60)
                if log:
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

        scanned += len(rows)
        changed += batch_changed

        if log and (scanned % 10000 < READ_BATCH or not rows):
            stats = semantic_parse_cache_stats()
            llm_calls = stats.get("llm_call", 0)
            cache_hits = (
                stats.get("memory_hit", 0)
                + stats.get("text_hit", 0)
                + stats.get("sqlite_hit", 0)
                + stats.get("text_sqlite_hit", 0)
            )
            print(
                f"  {table}: scanned {scanned:,}, changed {changed:,}, last_id={last_id}"
                f" | llm={llm_calls:,}, cache_hit={cache_hits:,}",
                flush=True,
            )

    return scanned, changed


def format_imported_snapshots(
    imported: dict[str, set[date | None]],
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """对本次导入写入的快照日期做字段格式化（含 LLM，当 PRODUCT_FORMAT_USE_LLM=true）。"""
    total_scanned = 0
    total_changed = 0
    for table in TABLES:
        snapshot_dates = imported.get(table)
        if not snapshot_dates:
            continue
        dates_label = ", ".join(
            sorted(
                ("NULL" if d is None else d.isoformat() for d in snapshot_dates),
                key=lambda s: (s == "NULL", s),
            )
        )
        print(
            f"LLM 字段格式化 {table}（snapshot_date: {dates_label}）...",
            flush=True,
        )
        scanned, changed = format_table(
            table,
            dry_run=dry_run,
            snapshot_dates=snapshot_dates,
        )
        total_scanned += scanned
        total_changed += changed
        verb = "would update" if dry_run else "updated"
        print(f"  {table}: scanned {scanned:,}, {verb} {changed:,}", flush=True)
    return total_scanned, total_changed
