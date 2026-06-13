#!/usr/bin/env bash
# 启动 Next.js + Tremor 仪表盘（固定 http://localhost:3000）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"

if [[ ! -f "$ROOT/database.env" && ! -f .env.local ]]; then
  echo "缺少 database.env 或 web/.env.local，请先配置 DATABASE_URL。" >&2
  echo "  cp ../database.env.example ../database.env" >&2
  echo "  或: npm run env:sync" >&2
  exit 1
fi

if lsof -ti:3000 >/dev/null 2>&1; then
  echo "端口 3000 已被占用。可先结束旧进程: lsof -ti:3000 | xargs kill" >&2
  echo "或访问终端里 next dev 打印的实际地址（可能是 3001）。" >&2
fi

npm run dev
