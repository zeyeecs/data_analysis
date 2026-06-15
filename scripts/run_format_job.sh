#!/usr/bin/env bash
# 服务器端商品字段格式化（brand/model 归一化、型号拆分）。
# 供 cron / systemd 调用；本地开发请优先在服务器跑，避免长连接占满本机。
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
LOG_FILE="${SJKX_FORMAT_LOG:-$LOG_DIR/format_job.log}"

# full：全表格式化（首次回填或修复后全量核对）
# reconcile：仅 brand 为 ['Hermes'] 等列表字面量的行（每日增量，快）
MODE="${SJKX_FORMAT_MODE:-reconcile}"

FORMAT_ARGS=(--write-db)
case "$MODE" in
  full)
    FORMAT_ARGS=(--write-db)
    ;;
  reconcile)
    FORMAT_ARGS=(--write-db --only-list-brand)
    ;;
  *)
    echo "未知 SJKX_FORMAT_MODE=$MODE（可用: full | reconcile）" >&2
    exit 2
    ;;
esac

{
  echo "=== $(date -Iseconds) format job start (mode=$MODE, cwd=$ROOT) ==="
  python3 -u scripts/format_product_fields.py "${FORMAT_ARGS[@]}"
  echo "=== $(date -Iseconds) format job done ==="
} 2>&1 | tee -a "$LOG_FILE"
