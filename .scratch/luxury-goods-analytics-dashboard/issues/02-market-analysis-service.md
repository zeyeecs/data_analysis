Status: ready-for-agent

# 市场分析服务与风险评估规则

## Parent

`.scratch/luxury-goods-analytics-dashboard/PRD.md`

## What to build

实现仪表盘背后的核心业务服务：输入 `modelId` 与商品成色，输出统一的市场分析结果，包括市场均价、建议最高收货价、风险等级、风险原因与趋势图数据。

该切片需要打通 Prisma 查询、最近 30 天价格时间序列聚合、成色折损系数、安全边际与近 3 日跌幅风险规则，并将这些逻辑封装为单一、可测试的服务接口，供页面直接消费。原始 SQL 可以通过 Prisma 的 `$queryRaw` 执行，但必须使用安全参数化，不能拼接裸 SQL。

本切片完成后，即使前端页面还未完善，也应能通过调用服务接口独立验证业务结果是否正确。

## Acceptance criteria

- [ ] 存在统一的市场分析服务接口，输入为 `modelId` 与成色，输出为稳定的分析结果结构
- [ ] 服务会查询最近 30 天价格时间序列，并返回可直接用于图表展示的日级数据
- [ ] 建议最高收货价按“市场均价 × 成色系数 × 安全边际”计算
- [ ] 风险规则至少覆盖默认安全状态与“近 3 个观测点中最新价格较第 3 个点下跌超过 5%”的预警状态
- [ ] 空 `modelId`、无样本数据、非法成色等错误场景会返回明确失败结果，而不是静默返回错误数据
- [ ] 至少为市场分析服务与风险规则补充自动化测试，验证主要输入输出行为

## Blocked by

- `.scratch/luxury-goods-analytics-dashboard/issues/01-dashboard-foundation.md`
