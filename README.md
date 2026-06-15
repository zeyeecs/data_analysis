# sjkx — 竞品已售数据 → Neon

将飞书云盘 **F / R / V** 三个目录中的 xlsx 导入 PostgreSQL：**三家竞品店铺的已售快照**，用于竞品对照分析（非自家在售库存）。

## 配置

| 文件 | 说明 |
|------|------|
| `.env` | 飞书 App 与三个竞品目录 token |
| `database.env` | Neon `DATABASE_URL` |

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 导入数据

默认 **累积保留**；默认 **仅导入库中尚无的 `snapshot_date`**（已有日期跳过，不再重复下载）；默认 **将图片下载并上传到 R2**，库中写入 R2 公开地址（需配置 `R2_*`）。

```bash
# 默认 4 个 xlsx 并行；只处理各表尚未入库的 snapshot_date
python3 scripts/import_to_tables.py --category F --category R --category V

# 强制重导目录内全部 xlsx，并对已有 snapshot_date 按日覆盖
python3 scripts/import_to_tables.py --reimport-all --category F

# 调高并行度（注意飞书 API 限流）
python3 scripts/import_to_tables.py --workers 6 --category F
```

可选：`--empty-images` / `--no-mirror-images`（跳过图片）、`--keep-image-urls`（仅调试：直接写飞书原链，不镜像 R2）。

若在 `.env` 中启用 `PRODUCT_FORMAT_USE_LLM=true` 并配置 `DEEPSEEK_API_KEY`（或其它 OpenAI 兼容 LLM），**每次导入新 snapshot_date 后会自动**对刚写入的行跑 LLM 型号/材质/颜色分类（与 `scripts/format_product_fields.py` 相同流程，按 `snapshot_date` 增量处理）。可用 `--skip-llm-format` 跳过。历史数据可手动：

```bash
python3 scripts/format_product_fields.py --write-db --snapshot-date 2026-05-01
```

## 恢复成色（撤销历史档位映射）

若库内 `condition` 曾被脚本映射为「全新 / 99新 / 98新 / 95」，**无法**用 SQL 反推飞书原值（多对一映射）。须从飞书 xlsx 按 `item_id` + `snapshot_date` 覆盖写回：

```bash
# 预览：统计将覆盖多少行（不写库）
python3 scripts/backfill_condition.py --restore --dry-run

# 写库：F / R / V 全部 xlsx，覆盖已有成色
python3 scripts/backfill_condition.py --restore

# 只处理单表、降低并行（飞书限流时）
python3 scripts/backfill_condition.py --restore --category F --workers 2
```

`--restore` 等价于 `--all-rows`（默认 `--all-rows` 未指定时仅填空成色）。导入逻辑已改为原样写入飞书表格中的成色文本。

## 回填图片（库内图片列为空时）

默认导入会清空图片列；若只补**尚无图片链接**的行、不重导其它字段，从飞书 xlsx 回填：

```bash
# 预览：统计将更新多少行（不写库）
python3 scripts/backfill_images.py --mirror-images --dry-run --category F

# 写库：镜像到 R2 后写入公开地址（推荐）
python3 scripts/backfill_images.py --mirror-images --category F

# 仅写入 xlsx 中的飞书原链（不经过 R2）
python3 scripts/backfill_images.py --keep-image-urls --category F

# 覆盖已有图片 URL（慎用）
python3 scripts/backfill_images.py --mirror-images --all-rows --category F
```

默认 **仅填空图片列**；`--mirror-images` 与 `import_to_tables` 行为一致（需 `.env` 中 `R2_*`）。

## 每日自动导入与格式化（服务器）

**导入、brand/model 格式化应在服务器或 GitHub Actions 上持续运行，不要在本地长跑。**

默认行为：增量导入新 `snapshot_date` → 新快照 LLM/规则格式化 → reconcile 列表字面量 brand（如 `['Hermes']`）。

```bash
# 服务器手动试跑（日志 logs/server_pipeline.log）
./scripts/run_server_pipeline.sh
```

**systemd timer（推荐）**：见 [`deploy/README.md`](deploy/README.md)。

```bash
sudo cp deploy/sjkx-pipeline.service.example /etc/systemd/system/sjkx-pipeline.service
sudo cp deploy/sjkx-pipeline.timer.example /etc/systemd/system/sjkx-pipeline.timer
# 编辑 User、WorkingDirectory
sudo systemctl daemon-reload
sudo systemctl enable --now sjkx-pipeline.timer
sudo systemctl start sjkx-pipeline.service   # 立即跑一次
```

**首次部署**：在服务器执行一次全表格式化（修复 R 表历史 brand）：

```bash
sudo cp deploy/sjkx-format-full.service.example /etc/systemd/system/sjkx-format-full.service
sudo systemctl start sjkx-format-full.service
```

**GitHub Actions**：`import.yml`（每日流水线）、`format.yml`（手动全表回填）；需在 Secrets 中配置 `DATABASE_URL`、飞书与 LLM 密钥。

旧版仅导入（无 reconcile）仍可用 `./scripts/run_daily_import.sh` 或 `sjkx-import.timer`，建议迁移到 `sjkx-pipeline`。

环境变量（可选）：`SJKX_LOG_DIR`、`SJKX_PIPELINE_LOG` 覆盖日志路径；`SJKX_FORMAT_MODE=full|reconcile` 控制格式化范围。

## 数据表（三家竞品 · 均为已售）

| 表 | 含义 | 分析角色 |
|----|------|----------|
| **F** | 竞品店 **F** 已售快照 | 两两对照常用锚定侧之一 |
| **R** | 竞品店 **R** 已售快照 | 与 F 并排对照 |
| **V** | 竞品店 **V** 已售快照 | 第三家竞品；含 `currency`、`sold_at` 等 |

- `snapshot_date`：自 xlsx 文件名解析；`imported_at`：入库时间。
- 领域术语与对照规则见 [`CONTEXT.md`](CONTEXT.md)。

## 分析前端

### Next.js + Tremor Dashboard（推荐，可部署 Vercel）

[`web/`](web/) 使用 [template-dashboard-oss](https://github.com/tremorlabs/template-dashboard-oss) 作为前端（Tremor 官方开源仪表盘模板），**仅保留 Neon 数据库连接**；图表与 KPI 数据来自 F / R / V 表，不再使用模板内置 mock 数据。

```bash
# 仓库根目录（推荐）
./scripts/run_web.sh

# 或手动
cd web
npm install
npm run env:sync   # 若尚无 web/.env.local
npm run dev
```

浏览器打开 **http://localhost:3000**（自动跳转到 `/overview`）。若提示端口占用：`lsof -ti:3000 | xargs kill`。发布前执行 `npm run build`。

### 部署到 Vercel

生产地址：**https://sjkx-analysis-web.vercel.app**

**不要在仓库根目录执行 `npx vercel`**：根目录会被误关联到 `project-dc6ac`，且 Vercel 会提示 `deploy/` 子目录（那是 systemd/nginx 配置，不是前端）。

```bash
# 仓库根目录（推荐）
./scripts/deploy_vercel.sh

# 或
cd web && npm install && npm run deploy
```

1. 在 Vercel 项目 **sjkx-analysis-web** 的环境变量中配置 `DATABASE_URL`（须为 Neon **pooler** 连接串，与 `database.env` 一致）。
2. 若从 Git 自动部署：项目 **Root Directory** 设为 `web`。

若 `npx vercel` 报 `EACCES`（`~/.npm` 含 root 文件）：在 `web/` 下已配置 `.npmrc` 使用本地缓存 `.npm-cache`，执行 `npm install` 后再 `npm run deploy` 即可。若要一劳永逸修复全局缓存：`sudo chown -R "$(whoami)" ~/.npm`

前端模板：[template-dashboard-oss](https://github.com/tremorlabs/template-dashboard-oss)（与 [tremor-npm](https://github.com/tremorlabs/tremor-npm) 同属 Tremor 生态，模板使用 Tremor Raw 组件 + Recharts）。

### Streamlit（本地快速查看）

**无注册、无向导**，打开即用：

```bash
cd /Users/lanse/Documents/sjkx
source .venv/bin/activate
pip install -r requirements.txt
./scripts/run_dashboard.sh
```

或：`streamlit run streamlit_app.py`

浏览器打开 **http://localhost:8501**（须保持终端窗口运行，不要关）。

若曾卡在 `Email:` 提示：项目已含 `.streamlit/credentials.toml` 可跳过；仍卡住时在终端**直接按回车**。

Metabase 为可选项（首次须注册向导），见 [`docs/analysis-frontend.md`](docs/analysis-frontend.md)。

## 对照分析（SQL / Notebook / CLI）

**最近邻配对**：锚定日与另表最近快照日相差 ≤3 天（平手取较早）。

`database.env` 里连接串含 `&` 时须写成 `DATABASE_URL='postgresql://...'`（单引号包裹）。**不要用** `source database.env`；Python 脚本会通过 `python-dotenv` 自动加载。

未安装 `psql` 时，用仓库脚本（推荐）：

```bash
# 自检：各表最近 snapshot_date 与行数
python3 scripts/db_query.py summary

# F 锚定 → R 两两对照
python3 scripts/db_query.py sql sql/shop_comparison.sql --anchor-date 2025-03-01

# V 锚定 → F、R 三方参照
python3 scripts/db_query.py sql sql/vestiaire_reference_comparison.sql --anchor-date 2025-03-05
```

已安装 PostgreSQL 客户端时也可用 `psql`：

```bash
psql "$DATABASE_URL" -v anchor_date="'2025-03-01'" -f sql/shop_comparison.sql
psql "$DATABASE_URL" -v anchor_date="'2025-03-05'" -f sql/vestiaire_reference_comparison.sql
```

## JupyterLab + Pandas

```bash
source .venv/bin/activate
pip install -r requirements.txt   # 含 jupyterlab、pandas、matplotlib
jupyter lab
```

在浏览器打开 `notebooks/sjkx_analysis.ipynb`：自检快照分布、运行两两/三方对照 SQL、按品牌汇总与简单图表。修改 notebook 中的 `ANCHOR_F` / `ANCHOR_V` 即可换锚定日。

## 测试

```bash
pytest
```
