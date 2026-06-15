#!/usr/bin/env bash
# 将 sjkx 同步到 VPS 并配置 systemd 流水线（默认 SSH Host: ziyong）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_HOST="${SJKX_SSH_HOST:-ziyong}"
REMOTE_DIR="${SJKX_REMOTE_DIR:-/home/ubuntu/sjkx}"

echo "==> sync to ${SSH_HOST}:${REMOTE_DIR}"
rsync -avz --delete \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '.npx-vercel-cache' \
  --exclude 'data/format_preview' \
  --exclude 'web/node_modules' \
  --exclude 'web/.next' \
  --exclude 'web/.npm-cache' \
  -e ssh \
  "$ROOT/" "${SSH_HOST}:${REMOTE_DIR}/"

echo "==> copy .env / database.env (if present)"
if [[ -f "$ROOT/.env" ]] || [[ -f "$ROOT/database.env" ]]; then
  ssh "$SSH_HOST" "chmod u+w ${REMOTE_DIR}/.env ${REMOTE_DIR}/database.env 2>/dev/null || true"
fi
if [[ -f "$ROOT/.env" ]]; then
  scp "$ROOT/.env" "${SSH_HOST}:${REMOTE_DIR}/.env"
fi
if [[ -f "$ROOT/database.env" ]]; then
  scp "$ROOT/database.env" "${SSH_HOST}:${REMOTE_DIR}/database.env"
fi
if [[ -f "$ROOT/data/semantic_parse_cache.db" ]]; then
  ssh "$SSH_HOST" "mkdir -p ${REMOTE_DIR}/data"
  rsync -avz -e ssh "$ROOT/data/semantic_parse_cache.db" "${SSH_HOST}:${REMOTE_DIR}/data/"
fi

echo "==> remote setup"
ssh "$SSH_HOST" "REMOTE_DIR='${REMOTE_DIR}' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p logs

for f in scripts/run_format_job.sh scripts/run_server_pipeline.sh; do
  chmod +x "$f"
done

# systemd（User=ubuntu，路径与 REMOTE_DIR 一致）
sudo tee /etc/systemd/system/sjkx-pipeline.service >/dev/null <<EOF
[Unit]
Description=sjkx daily import + product field format (F/R/V)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
Group=ubuntu
WorkingDirectory=${REMOTE_DIR}
Environment=PATH=${REMOTE_DIR}/.venv/bin:/usr/bin:/bin
EnvironmentFile=-${REMOTE_DIR}/.env
ExecStart=${REMOTE_DIR}/scripts/run_server_pipeline.sh
UnsetEnvironment=DATABASE_URL

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/sjkx-pipeline.timer >/dev/null <<EOF
[Unit]
Description=Run sjkx import + format pipeline daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

sudo tee /etc/systemd/system/sjkx-format-full.service >/dev/null <<EOF
[Unit]
Description=sjkx full product field format (F/R/V all rows)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
Group=ubuntu
WorkingDirectory=${REMOTE_DIR}
Environment=PATH=${REMOTE_DIR}/.venv/bin:/usr/bin:/bin
EnvironmentFile=-${REMOTE_DIR}/.env
Environment=SJKX_FORMAT_MODE=full
ExecStart=${REMOTE_DIR}/scripts/run_format_job.sh
UnsetEnvironment=DATABASE_URL

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sjkx-pipeline.timer
sudo systemctl start sjkx-pipeline.timer
echo "timer enabled; status:"
sudo systemctl status sjkx-pipeline.timer --no-pager || true
REMOTE

echo "==> done. 首次全表格式化（后台）:"
echo "  ssh ${SSH_HOST} 'sudo systemctl start sjkx-format-full.service'"
echo "  ssh ${SSH_HOST} 'journalctl -u sjkx-format-full.service -f'"
