"""Notebook / 脚本共用的对照 SQL 与快照汇总。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import ROOT

SQL_DIR = ROOT / "sql"


def substitute_anchor_date(sql: str, anchor: date) -> str:
    return sql.replace(":'anchor_date'::date", f"'{anchor.isoformat()}'::date")


def load_sql(path: Path | str, anchor: date | None = None) -> str:
    text = Path(path).read_text(encoding="utf-8")
    if anchor is not None:
        text = substitute_anchor_date(text, anchor)
    return text


def fetch_snapshot_summary(conn, limit: int = 20) -> pd.DataFrame:
    lim = int(limit)
    q = f"""
    SELECT * FROM (
        SELECT 'F' AS tbl, snapshot_date, COUNT(*)::bigint AS rows
        FROM "F" GROUP BY snapshot_date ORDER BY snapshot_date DESC LIMIT {lim}
    ) f
    UNION ALL
    SELECT * FROM (
        SELECT 'R' AS tbl, snapshot_date, COUNT(*)::bigint AS rows
        FROM "R" GROUP BY snapshot_date ORDER BY snapshot_date DESC LIMIT {lim}
    ) r
    UNION ALL
    SELECT * FROM (
        SELECT 'V' AS tbl, snapshot_date, COUNT(*)::bigint AS rows
        FROM "V" GROUP BY snapshot_date ORDER BY snapshot_date DESC LIMIT {lim}
    ) v
    ORDER BY tbl, snapshot_date DESC
    """
    return pd.read_sql(q, conn)


def fetch_table_bounds(conn) -> dict[str, tuple[date | None, date | None]]:
    """每表 (min_snapshot_date, max_snapshot_date)，一次往返。"""
    q = """
    SELECT 'F' AS tbl, MIN(snapshot_date) AS min_d, MAX(snapshot_date) AS max_d
    FROM "F" WHERE snapshot_date IS NOT NULL
    UNION ALL
    SELECT 'R', MIN(snapshot_date), MAX(snapshot_date)
    FROM "R" WHERE snapshot_date IS NOT NULL
    UNION ALL
    SELECT 'V', MIN(snapshot_date), MAX(snapshot_date)
    FROM "V" WHERE snapshot_date IS NOT NULL
    """
    df = pd.read_sql(q, conn)
    out: dict[str, tuple[date | None, date | None]] = {}
    for _, row in df.iterrows():
        mn = row["min_d"]
        mx = row["max_d"]
        out[str(row["tbl"])] = (
            mn.date() if hasattr(mn, "date") else mn,
            mx.date() if hasattr(mx, "date") else mx,
        )
    return out


def fetch_latest_snapshot_dates(conn) -> dict[str, date | None]:
    bounds = fetch_table_bounds(conn)
    return {tbl: mx for tbl, (_, mx) in bounds.items()}


def fetch_latest_snapshot_dates_from_bounds(
    bounds: dict[str, tuple[date | None, date | None]],
) -> dict[str, date | None]:
    return {tbl: mx for tbl, (_, mx) in bounds.items()}


def run_comparison(conn, sql_name: str, anchor: date) -> pd.DataFrame:
    sql = load_sql(SQL_DIR / sql_name, anchor)
    return pd.read_sql(sql, conn)


def fetch_snapshot_date_list(conn, table: str) -> list[date]:
    df = pd.read_sql(
        f'SELECT DISTINCT snapshot_date AS d FROM "{table}" '
        f"WHERE snapshot_date IS NOT NULL ORDER BY d",
        conn,
    )
    out: list[date] = []
    for val in df["d"]:
        out.append(val.date() if hasattr(val, "date") else val)
    return out


def fetch_integrated_sales(
    conn,
    *,
    f_date: date | None,
    r_date: date | None,
    v_date: date | None,
    detail: str = "brand",
) -> pd.DataFrame:
    name = (
        "competitor_sales_integrated.sql"
        if detail == "catalog"
        else "competitor_sales_integrated_brand.sql"
    )
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    params = (f_date, f_date, r_date, r_date, v_date, v_date)
    return pd.read_sql(sql, conn, params=params)


def fetch_integrated_sales_range(
    conn,
    start: date,
    end: date,
    *,
    by_day: bool = False,
    detail: str = "brand",
) -> pd.DataFrame:
    """detail: brand（默认，行少、传输快）| catalog（型号+成色明细）。"""
    if start > end:
        start, end = end, start
    if by_day:
        name = "competitor_sales_integrated_range_daily.sql"
    elif detail == "catalog":
        name = "competitor_sales_integrated_range.sql"
    else:
        name = "competitor_sales_integrated_range_brand.sql"
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    params = (start, end, start, end, start, end)
    return pd.read_sql(sql, conn, params=params)


def model_ilike_pattern(keyword: str) -> str:
    return f"%{keyword.strip()}%"


def fetch_model_sales_range(
    conn,
    start: date,
    end: date,
    model_keyword: str,
    *,
    by_day: bool = False,
) -> pd.DataFrame:
    """按型号关键字（部分匹配）查询三店整合数据。"""
    if start > end:
        start, end = end, start
    pat = model_ilike_pattern(model_keyword)
    name = "model_sales_range_daily.sql" if by_day else "model_sales_range.sql"
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    params = (start, end, pat, start, end, pat, start, end, pat)
    return pd.read_sql(sql, conn, params=params)


def fetch_model_sales_single(
    conn,
    *,
    f_date: date | None,
    r_date: date | None,
    v_date: date | None,
    model_keyword: str,
) -> pd.DataFrame:
    pat = model_ilike_pattern(model_keyword)
    sql = (SQL_DIR / "model_sales_single.sql").read_text(encoding="utf-8")
    params = (f_date, f_date, pat, r_date, r_date, pat, v_date, v_date, pat)
    return pd.read_sql(sql, conn, params=params)


def fetch_model_price_trend(
    conn,
    start: date,
    end: date,
    model_keyword: str,
) -> pd.DataFrame:
    """按型号汇总全渠道日度价格（不区分店铺）。"""
    if start > end:
        start, end = end, start
    pat = model_ilike_pattern(model_keyword)
    sql = (SQL_DIR / "model_price_trend_daily.sql").read_text(encoding="utf-8")
    params = (start, end, pat, start, end, pat, start, end, pat)
    df = pd.read_sql(sql, conn, params=params)
    if df.empty:
        return df
    df["avg_price"] = df["total_price"] / df["item_count"].replace(0, pd.NA)
    for col in ("snapshot_date",):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    return df


def fetch_shop_daily_trends(conn, start: date, end: date) -> pd.DataFrame:
    """各店按 snapshot_date 汇总件数与总额，用于趋势图。"""
    if start > end:
        start, end = end, start
    sql = (SQL_DIR / "shop_daily_trends.sql").read_text(encoding="utf-8")
    params = (start, end, start, end, start, end)
    df = pd.read_sql(sql, conn, params=params)
    if df.empty:
        return df
    df["avg_price"] = df["total_price"] / df["item_count"].replace(0, pd.NA)
    for col in ("snapshot_date",):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    return df


def default_period_bounds(
    bounds: dict[str, tuple[date | None, date | None]],
    *,
    days: int = 14,
) -> tuple[date, date]:
    """根据各表 min/max 快照日，给出默认时间段（最近 days 天）。"""
    mins: list[date] = []
    maxs: list[date] = []
    for mn, mx in bounds.values():
        if mn is not None:
            mins.append(mn)
        if mx is not None:
            maxs.append(mx)
    if not maxs:
        today = date.today()
        return today - timedelta(days=days), today
    end = max(maxs)
    data_start = min(mins) if mins else end
    start = max(data_start, end - timedelta(days=days))
    return start, end
