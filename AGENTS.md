# sjkx — Agent 说明

## 文档语言

本仓库内由 Agent 或 skill **新建或改写**的 Markdown 文档一律使用**简体中文**，包括：

- `.scratch/` 下的 PRD、issue、评论
- `CONTEXT.md`、`docs/adr/` 下的架构决策记录
- `docs/` 下其它说明文档

**例外（保持英文，勿翻译）：**

- 代码标识符、文件路径、命令、环境变量名
- Git / issue **状态标签**字符串（见 `docs/agents/triage-labels.md`）
- 第三方 API、数据库表名/列名（如 `F`、`R`、`V`、`snapshot_date`）

## Agent skills

### Issue tracker

任务与 PRD 通过 Linear MCP 跟踪，组织为 `cryogrid`、项目为 `二奢数据分析`。详见 `docs/agents/issue-tracker.md`。

### Triage labels

五种分诊状态及对应标签字符串。详见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：仓库根目录 `CONTEXT.md` 与 `docs/adr/`。详见 `docs/agents/domain.md`。
