# 服务器部署（导入 + 格式化）

竞品数据导入与 **brand/model 字段格式化** 应在服务器上持续运行，**不要在本地 Mac 上长跑**。

**当前 VPS**（SSH 配置 `Host ziyong`）：

| 项 | 值 |
|----|-----|
| 地址 | `ubuntu@1.14.101.46`，端口 `741` |
| 项目路径 | `/home/ubuntu/sjkx` |
| 每日任务 | `sjkx-pipeline.timer`，本地时间 **03:00** |
| 日志 | `logs/server_pipeline.log`、`logs/format_job.log` |

本地一键同步部署：

```bash
./scripts/deploy_vps.sh
```

## 首次部署（手动步骤）

```bash
# 1. 克隆到服务器（示例路径 /opt/sjkx）
sudo mkdir -p /opt/sjkx && sudo chown deploy:deploy /opt/sjkx
git clone <repo-url> /opt/sjkx
cd /opt/sjkx

# 2. Python 环境与依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. 配置（从本机 scp 或手填，勿提交仓库）
#   .env          — 飞书、LLM、R2
#   database.env  — Neon DATABASE_URL

# 4. systemd：每日流水线（导入 + reconcile）
sudo cp deploy/sjkx-pipeline.service.example /etc/systemd/system/sjkx-pipeline.service
sudo cp deploy/sjkx-pipeline.timer.example /etc/systemd/system/sjkx-pipeline.timer
# 编辑 User、WorkingDirectory、EnvironmentFile 路径
sudo systemctl daemon-reload
sudo systemctl enable --now sjkx-pipeline.timer

# 5. 首次全表格式化（修复 R 表 ['Hermes'] 等历史 brand）
sudo cp deploy/sjkx-format-full.service.example /etc/systemd/system/sjkx-format-full.service
sudo systemctl daemon-reload
sudo systemctl start sjkx-format-full.service
journalctl -u sjkx-format-full.service -f
```

## 日常行为

| 步骤 | 脚本 | 说明 |
|------|------|------|
| 每日 03:00 | `run_server_pipeline.sh` | 增量导入新 snapshot + reconcile 列表 brand |
| 导入内嵌 | `import_to_tables.py` | 新写入行从 `old_data` 做 LLM/规则格式化 |
| reconcile | `run_format_job.sh` | `brand LIKE '[%'` 的行归一化为 `hermes` 等 |

日志默认：`logs/server_pipeline.log`、`logs/format_job.log`。

## 回填 old_data（历史行）

`old_data` 列存在但为空时，从飞书 xlsx 写入 JSON 快照（**不改** brand/model 等其它列）：

```bash
cd /home/ubuntu/sjkx && source .venv/bin/activate

# 预览
python3 scripts/backfill_old_data.py

# 写库
python3 scripts/backfill_old_data.py --write-db --workers 4

# 后台跑（推荐）
nohup python3 -u scripts/backfill_old_data.py --write-db --workers 4 \
  >> logs/backfill_old_data.log 2>&1 &
tail -f logs/backfill_old_data.log
```

回填完成后，用 `old_data.model` 重新格式化：

```bash
SJKX_FORMAT_MODE=full ./scripts/run_format_job.sh
```

## 环境变量

在 `.env` 中建议开启（服务器上配置，勿在本地重复跑）：

```bash
PRODUCT_FORMAT_USE_LLM=true
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

`SEMANTIC_PARSE_CACHE_PATH` 默认 `data/semantic_parse_cache.db`，随仓库保留可加速重复解析。

## 从旧 sjkx-import 迁移

```bash
sudo systemctl disable --now sjkx-import.timer
sudo systemctl enable --now sjkx-pipeline.timer
```

## GitHub Actions（无自有 VPS 时）

仓库 `.github/workflows/import.yml` 与 `format.yml` 可在云端执行同等流水线；在仓库 Secrets 中配置 `DATABASE_URL`、飞书与 LLM 密钥。
