Status: ready-for-agent

# 对照查询文档与 Neon 运行说明

## Parent

`.scratch/cross-channel-comparison/PRD.md`

## What to build

在 README（或 `docs/` 下专页，与仓库文档语言约定一致）补充 **可复用对照查询** 的使用说明：如何设置锚定 `snapshot_date`、如何执行 **店铺间对照** 与 **Vestiaire 参照对照**、各 **目录聚合指标** 含义简述。

写明 **导入自检**：**分表导入** 后对照前须确认 F/R/V 是否存在可 **最近邻配对** 的 **快照**（含只更新 f店未更新 r店的情形）。链到 `CONTEXT.md` 术语（**挂牌价**、**成交参考价**、**对照快照对** 等）。

不实现 API/UI；不展开 **汇率换算** 操作步骤（仅可提及远期 ADR-0002）。

## Acceptance criteria

- [ ] README 或 docs 中有独立「对照分析」小节，含至少各一条 **店铺间对照**、**Vestiaire 参照对照** 的 Neon 执行示例
- [ ] 文档说明锚定日期参数、±3 天 **最近邻配对** 及无配对时的预期行为
- [ ] 文档包含 **导入自检** 清单（分表导入、两侧快照新旧）
- [ ] 文档使用 `CONTEXT.md` 中的领域用语，无实现细节堆砌

## Blocked by

- `.scratch/cross-channel-comparison/issues/02-shop-comparison-sql.md`
- `.scratch/cross-channel-comparison/issues/03-vestiaire-reference-sql.md`
