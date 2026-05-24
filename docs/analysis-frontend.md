# 分析前端（Streamlit）

**默认推荐**：[`streamlit_app.py`](../streamlit_app.py) — 打开浏览器即分析，**无注册、无向导、无产品选型页**。

```bash
source .venv/bin/activate
pip install streamlit
./scripts/run_dashboard.sh
```

浏览器 http://localhost:8501 — 终端须保持运行；若出现 `Email:` 提示，直接按回车。

浏览器自动打开 http://localhost:8501 ，三个标签页：

| 标签 | 内容 |
|------|------|
| 快照分布 | F/R/V 各 `snapshot_date` 行数 |
| F 对 R | `sql/shop_comparison.sql` |
| V 三方参照 | `sql/vestiaire_reference_comparison.sql` |

左侧栏选择锚定日；默认取各表最新 `snapshot_date`。

---

## Metabase（可选）

需要拖拽建仪表盘、多用户权限时再用 [Metabase](https://github.com/metabase/metabase)。首次自托管须完成注册向导；若不想走该流程，请直接用 Streamlit。

```bash
docker compose -f docker-compose.metabase.yml up -d
# http://localhost:3000
```

详见 [`metabase-setup.md`](metabase-setup.md)（含 Docker 故障排除、Neon 连接、`sql/metabase/` SQL）。
