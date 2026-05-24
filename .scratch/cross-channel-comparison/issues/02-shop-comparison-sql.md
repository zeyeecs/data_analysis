Status: ready-for-agent

# 店铺间对照可复用 SQL（f店锚定 → r店）

## Parent

`.scratch/cross-channel-comparison/PRD.md`

## What to build

交付一条可在 Neon 执行的 **店铺间对照** 查询：以 f店（表 F）某 `snapshot_date` 为锚，在 r店（表 R）可用 **快照** 日上应用 **最近邻配对**（≤3 天，语义与 issue 01 测试向量一致），对两侧分别按 **品牌 / 型号 / 成色** 做 **目录聚合对照**，输出全套 **目录聚合指标**（件数、均价、最低价、最高价、中位数、标价总额），f店/r店均使用 **挂牌价**。

无有效 **对照快照对** 时，查询应返回空结果或等价可辨识的「无配对」状态（勿静默混用错误日期）。

支持参数化锚定日期（如 psql `\set` 或文档化占位符），便于重复执行。可选：用 issue 01 的测试向量写一条对照 SQL 的 fixture/集成测试；至少提供可在 Neon 手动验证的说明。

## Acceptance criteria

- [ ] 存在可复用的 **店铺间对照** SQL（或等价脚本），默认 f店锚定、r店配对
- [ ] 聚合维度含 brand、model、condition；指标含 count、avg、min、max、median、sum(price)
- [ ] 最近邻规则为日历差最小且 ≤3 天；>3 天时不产出配对行
- [ ] 与 issue 01 配对器对同一组测试日期的结果一致（文档或自动化断言至少一种）
- [ ] 不依赖 **商品对齐** 或跨表 `item_id` join

## Blocked by

- `.scratch/cross-channel-comparison/issues/01-nearest-snapshot-pairing.md`
