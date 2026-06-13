#!/usr/bin/env bash
# 从飞书 xlsx 覆盖恢复 F/R/V 的 condition 列（撤销历史成色档位映射）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python3 scripts/backfill_condition.py --restore "$@"
