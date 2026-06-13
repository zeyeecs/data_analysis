#!/usr/bin/env bash
# 每日增量导入：从飞书 F/R/V 目录拉取库中尚无 snapshot_date 的 xlsx 写入 Neon。
# 供 cron / systemd timer 调用；也可手动执行。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .venv/bin/activate ]]; then
  echo "未找到 .venv，请先在仓库根目录执行: python3 -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 避免 shell 里错误的 DATABASE_URL 覆盖 database.env
unset DATABASE_URL 2>/dev/null || true

LOG_DIR="${SJKX_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="${SJKX_IMPORT_LOG:-$LOG_DIR/daily_import.log}"

{
  echo "=== $(date -Iseconds) daily import start (cwd=$ROOT) ==="
  python3 -u scripts/import_to_tables.py --category F --category R --category V
  echo "=== $(date -Iseconds) daily import done ==="
} 2>&1 | tee -a "$LOG_FILE"
