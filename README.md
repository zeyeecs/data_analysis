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

默认 **累积保留**；默认 **仅导入库中尚无的 `snapshot_date`**（已有日期跳过，不再重复下载）；默认 **图片列留空**，只导品牌/型号/成色/价格等。

```bash
# 默认 4 个 xlsx 并行；只处理各表尚未入库的 snapshot_date
python3 scripts/import_to_tables.py --category F --category R --category V

# 强制重导目录内全部 xlsx，并对已有 snapshot_date 按日覆盖
python3 scripts/import_to_tables.py --reimport-all --category F

# 调高并行度（注意飞书 API 限流）
python3 scripts/import_to_tables.py --workers 6 --category F
```

可选：`--keep-image-urls`（写入 xlsx 中的链接）、`--mirror-images`（下载并上传到 R2，见 `.env` 中 `R2_*`）。

## 数据表（三家竞品 · 均为已售）

| 表 | 含义 | 分析角色 |
|----|------|----------|
| **F** | 竞品店 **F** 已售快照 | 两两对照常用锚定侧之一 |
| **R** | 竞品店 **R** 已售快照 | 与 F 并排对照 |
| **V** | 竞品店 **V** 已售快照 | 第三家竞品；含 `currency`、`sold_at` 等 |

- `snapshot_date`：自 xlsx 文件名解析；`imported_at`：入库时间。
- 领域术语与对照规则见 [`CONTEXT.md`](CONTEXT.md)。

## 分析前端（Streamlit，推荐）

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
