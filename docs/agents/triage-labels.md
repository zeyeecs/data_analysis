# 分诊标签

mattpocock/skills 使用五种标准分诊角色。本文件将角色映射为本仓库 issue 中实际使用的**标签字符串**（写入 `Status:` 行，保持英文以便与 skill 兼容）。

| 标准角色 | 本仓库标签 | 含义 |
| -------- | ---------- | ---- |
| `needs-triage` | `needs-triage` | 维护者尚未评估 |
| `needs-info` | `needs-info` | 等待报告人补充信息 |
| `ready-for-agent` | `ready-for-agent` | 已写清，可由 Agent 独立执行 |
| `ready-for-human` | `ready-for-human` | 需要人工实现或决策 |
| `wontfix` | `wontfix` | 不予处理 |

当 skill 提到某一角色（例如「打上 ready-for-agent 标签」）时，使用上表「本仓库标签」列中的字符串。

若你改用其它标签名，只改右列；skill 侧角色名不变。
