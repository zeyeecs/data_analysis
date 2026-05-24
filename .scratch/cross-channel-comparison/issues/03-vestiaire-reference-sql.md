Status: ready-for-agent

# Vestiaire 参照对照可复用 SQL（V 锚定 → f店、r店）

## Parent

`.scratch/cross-channel-comparison/PRD.md`

## What to build

交付 **Vestiaire 参照对照** 查询：以 V 表某 `snapshot_date` 为锚，分别在 F、R 上各做一次 **最近邻配对**（≤3 天，与 issue 01 一致），得到两条独立对照链（f店相对 V、r店相对 V），互不替代。

对 V 侧按 **成交参考价**（`price`）及 **品牌 / 型号 / 成色** 聚合，并保留 `currency` 分组以便 **汇率换算** 未就绪时按币种查看；不按 `sold_at` 另设时间窗。对 f店/r店侧使用 **挂牌价** 与相同 **目录聚合指标** 集合。

参数化 V 的锚定 `snapshot_date`，可在 Neon 重复执行。

## Acceptance criteria

- [ ] 存在可复用的 **Vestiaire 参照对照** SQL（或等价脚本），V 为锚定侧
- [ ] 对同一锚定日，分别输出 f店、r店两侧的聚合结果（两条配对链）
- [ ] V 侧聚合含 `currency` 维度；使用 **成交参考价** 而非 seller_price
- [ ] 最近邻 ≤3 天；无配对时不混用错误日期
- [ ] 与 issue 01 配对语义一致；不实现 **汇率换算** 列（可留注释扩展点）

## Blocked by

- `.scratch/cross-channel-comparison/issues/01-nearest-snapshot-pairing.md`
