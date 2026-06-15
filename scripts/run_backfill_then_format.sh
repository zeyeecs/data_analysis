#!/usr/bin/env bash
# 回填 old_data → 全表格式化（历史数据一次性修复）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate
unset DATABASE_URL 2>/dev/null || true

LOG_DIR="${SJKX_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"

{
  echo "=== $(date -Iseconds) backfill old_data start ==="
  python3 -u scripts/backfill_old_data.py --write-db --workers "${IMPORT_WORKERS:-4}"
  echo "=== $(date -Iseconds) backfill old_data done ==="

  echo "=== $(date -Iseconds) full format start ==="
  SJKX_FORMAT_MODE=full SJKX_FORMAT_LOG="$LOG_DIR/format_after_backfill.log" \
    "$ROOT/scripts/run_format_job.sh"
  echo "=== $(date -Iseconds) full format done ==="
} 2>&1 | tee -a "$LOG_DIR/backfill_then_format.log"
