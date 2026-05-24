#!/usr/bin/env bash
# 服务器部署：监听 0.0.0.0，供本机 Nginx 反代或内网访问
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

PORT="${STREAMLIT_PORT:-8501}"
BIND="${STREAMLIT_BIND:-0.0.0.0}"

unset DATABASE_URL 2>/dev/null || true

exec streamlit run streamlit_app.py \
  --server.port="${PORT}" \
  --server.address="${BIND}" \
  --server.headless=true
