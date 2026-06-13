#!/usr/bin/env bash
# 从飞书恢复被覆盖字段 → 导出 old_data → 按 old_data 格式化写库
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-data/format_preview/restore_$(date -u +%Y%m%dT%H%M%SZ)}"
WORKERS="${IMPORT_WORKERS:-4}"
DRY_RUN="${DRY_RUN:-}"

echo "==> 1/3 从飞书恢复 brand/model/color 等原值"
if [[ "$DRY_RUN" == "1" ]]; then
  python3 scripts/backfill_feishu_fields.py --restore --dry-run --workers "$WORKERS"
else
  python3 scripts/backfill_feishu_fields.py --restore --workers "$WORKERS"
fi

echo "==> 2/3 导出 JSONL（含 old_data）→ $OUT_DIR"
python3 scripts/export_format_preview.py --output-dir "$OUT_DIR"

echo "==> 3/3 用 old_data 格式化并写库"
if [[ "$DRY_RUN" == "1" ]]; then
  python3 scripts/backfill_from_old_data.py --input-dir "$OUT_DIR"
else
  python3 scripts/backfill_from_old_data.py --input-dir "$OUT_DIR" --write-db
fi

echo "done → $OUT_DIR"
