#!/usr/bin/env python3
"""删除遗留表 feishu_files / feishu_file_rows（不触发 F/R/V 导入）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db import drop_legacy_tables


def main() -> int:
    load_config()
    print("正在删除 feishu_file_rows / feishu_files（可能需数分钟）...", flush=True)
    drop_legacy_tables()
    print("旧表已删除。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
