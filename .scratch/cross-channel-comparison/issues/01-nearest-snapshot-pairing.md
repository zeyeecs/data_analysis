Status: ready-for-agent

# 最近邻配对器与快照日解析单测

## Parent

`.scratch/cross-channel-comparison/PRD.md`

## What to build

实现可独立测试的 **最近邻配对器**：给定锚定 `snapshot_date` 与候选日期列表，返回日历差最小且 `abs(delta) <= 3` 的配对日；超过 3 天或无候选时返回「无配对」。平手（相同最小日差）时固定取 **较早日期**，行为写入测试以防漂移。

将文件名 → `snapshot_date` 的 **快照日解析器** 与现有 xlsx 导入逻辑对齐，并为已知格式（中文「年月日」、`_YYYYMMDD_` 等）补充单测。

该模块不访问数据库；输出语义须与后续 **可复用对照查询** 一致，供 SQL 实现对照时使用同一套测试向量验证。

配对状态机（决策摘要，来自 PRD）：

```
paired = argmin |d - anchor_d|  for d in candidates
if paired is None or |paired - anchor_d| > 3: 无配对
else: 对照快照对 = (anchor_d, paired)
平手: 取较早日期
```

## Acceptance criteria

- [ ] 存在可导入的配对函数（或等价小模块），接口为「锚定日 + 候选日列表 → 配对日或 None」
- [ ] 单测覆盖：差 0/1/3 天可配对；差 4 天无配对；空候选无配对；平手取较早日
- [ ] 单测覆盖：至少两种文件名日期格式解析正确；无法解析时返回 None
- [ ] `pytest` 在干净环境中可通过（新增依赖写入 `requirements.txt` 若需要）

## Blocked by

None - can start immediately
