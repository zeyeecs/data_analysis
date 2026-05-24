#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

PORT="${STREAMLIT_PORT:-8501}"
URL="http://localhost:${PORT}"

# 避免 shell 里错误的 DATABASE_URL 覆盖 database.env
unset DATABASE_URL 2>/dev/null || true

if curl -sf "${URL}/_stcore/health" >/dev/null 2>&1; then
  echo "分析页已在运行: ${URL}"
  echo "（若要重启，先执行: pkill -f 'streamlit run streamlit_app.py'）"
  exit 0
fi

if lsof -i ":${PORT}" >/dev/null 2>&1; then
  echo "端口 ${PORT} 被其它程序占用，请关闭后重试，或: STREAMLIT_PORT=8502 ./scripts/run_dashboard.sh"
  exit 1
fi

exec streamlit run streamlit_app.py --server.port="${PORT}"
