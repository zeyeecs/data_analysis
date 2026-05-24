#!/usr/bin/env python3
"""在 Neon 上创建性能索引（可重复执行）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db import db_session


def main() -> None:
    load_config()
    sql_path = ROOT / "sql" / "add_perf_indexes.sql"
    statements = [s.strip() for s in sql_path.read_text(encoding="utf-8").split(";") if s.strip()]
    with db_session() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                print(stmt.split("\n")[0], "...")
                cur.execute(stmt)
    print("完成：", len(statements), "个索引已就绪。")


if __name__ == "__main__":
    main()
