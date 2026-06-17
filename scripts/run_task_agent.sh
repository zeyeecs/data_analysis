#!/usr/bin/env bash
# VPS 端 AI 任务 HTTP 代理（供 Vercel 远程触发 Python 流水线）
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
mkdir -p logs/ai-tasks

exec python3 -u -m src.task_agent.server "$@"
