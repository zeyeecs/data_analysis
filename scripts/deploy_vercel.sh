#!/usr/bin/env bash
# 发布 Next.js 仪表盘到 Vercel（项目 sjkx-analysis-web）
# 勿在仓库根目录执行 npx vercel，否则会误关联 project-dc6ac。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"
exec npm run deploy -- "$@"
