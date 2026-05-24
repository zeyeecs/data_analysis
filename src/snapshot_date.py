from __future__ import annotations

import re
from datetime import date


def parse_snapshot_date(filename: str) -> date | None:
    """从 xlsx 文件名解析 snapshot_date。"""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", filename)
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_", filename)
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", filename.replace("：", ":"))
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    return None
