#!/usr/bin/env bash
# 服务器每日流水线：飞书增量导入 → 新快照字段格式化 → brand 列表字面量 reconcile。
# 替代单独 run_daily_import.sh；systemd timer 应调用本脚本。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .venv/bin/activate ]]; then
  echo "未找到 .venv，请先在仓库根目录执行: python3 -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

unset DATABASE_URL 2>/dev/null || true

LOG_DIR="${SJKX_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="${SJKX_PIPELINE_LOG:-$LOG_DIR/server_pipeline.log}"

{
  echo "=== $(date -Iseconds) server pipeline start (cwd=$ROOT) ==="

  echo "--- 1/2 飞书增量导入 F/R/V（含新快照 LLM 格式化）---"
  python3 -u scripts/import_to_tables.py --category F --category R --category V

  echo "--- 2/2 brand 列表字面量 reconcile（R 表等历史快照）---"
  SJKX_FORMAT_MODE=reconcile SJKX_FORMAT_LOG="$LOG_DIR/format_reconcile.log" \
    "$ROOT/scripts/run_format_job.sh"

  echo "=== $(date -Iseconds) server pipeline done ==="
} 2>&1 | tee -a "$LOG_FILE"
