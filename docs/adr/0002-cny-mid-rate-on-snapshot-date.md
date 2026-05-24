# 汇率换算以 CNY 为基准，按快照日公开中间价

跨币种 **Vestiaire 参照对照** 等场景需要将 V 的 `currency` 统一后再与 f店、r店的 **挂牌价**（已为 CNY 口径）比较。选定 **基准货币** 为 CNY；**汇率来源** 为各 `snapshot_date` 当日的公开中间价，入库内汇率表后换算，不在导入 xlsx 时换汇。

**Considered Options:** 手动维护汇率（灵活但易与快照日脱节）；以 EUR/USD 为基准（与当前 f店/r店记账习惯不符）。
