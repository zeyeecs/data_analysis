#!/usr/bin/env python3
"""无需 psql：自检快照分布、执行对照 SQL。"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.analysis import fetch_snapshot_summary, load_sql
from src.config import load_config
from src.db import db_session, get_connection


def cmd_summary(limit: int) -> int:
    load_config()
    conn = get_connection()
    try:
        df = fetch_snapshot_summary(conn, limit=limit)
    finally:
        conn.close()
    for table in ("F", "R", "V"):
        part = df[df["tbl"] == table]
        print(f'\n==> 表 "{table}"（最近 {limit} 个 snapshot_date）')
        if part.empty:
            print("  （无数据）")
            continue
        for _, row in part.iterrows():
            print(f"  {row['snapshot_date']}\t{row['rows']} 行")
    return 0


def cmd_run_sql(sql_path: Path, anchor: date) -> int:
    load_config()
    sql = load_sql(sql_path, anchor)
    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                print("（无结果集）")
                return 0
            cols = [d[0] for d in cur.description]
            print("\t".join(cols))
            rows = cur.fetchall()
            max_rows = 100
            for row in rows[:max_rows]:
                print("\t".join("" if v is None else str(v) for v in row))
            if len(rows) > max_rows:
                print(f"... 共 {len(rows)} 行，仅显示前 {max_rows}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Neon 查询（不依赖 psql）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sum = sub.add_parser("summary", help="各表 snapshot_date 行数（自检）")
    p_sum.add_argument("--limit", type=int, default=10)

    p_sql = sub.add_parser("sql", help="执行对照 SQL（替换 anchor_date）")
    p_sql.add_argument("sql_file", type=Path)
    p_sql.add_argument("--anchor-date", required=True, help="YYYY-MM-DD")

    args = parser.parse_args()
    if args.command == "summary":
        return cmd_summary(args.limit)
    anchor = date.fromisoformat(args.anchor_date)
    return cmd_run_sql(args.sql_file, anchor)


if __name__ == "__main__":
    raise SystemExit(main())
