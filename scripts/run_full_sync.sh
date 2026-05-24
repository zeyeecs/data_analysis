#!/usr/bin/env bash
# 已废弃：旧版 sync_feishu_to_db.py 会写入 feishu_files（含 BYTEA），请改用 import_to_tables.py
set -euo pipefail
echo "run_full_sync.sh 已废弃，请使用: python3 scripts/import_to_tables.py" >&2
exit 1
