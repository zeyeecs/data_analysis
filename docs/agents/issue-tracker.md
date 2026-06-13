# Issue 跟踪：Linear MCP

本仓库的任务、PRD 与实现工单以 **Linear MCP** 作为主 issue tracker。

## 目标工作区

- 组织名称：`cryogrid`
- 项目名称：`二奢数据分析`

工程类 skill 在创建、读取、分诊或拆分任务时，应默认面向上述 Linear 组织与项目执行。

## 认证约定

- API key 不写入仓库文档或源码文件
- 运行 Linear 相关流程时，从环境变量 **`LINEAR_API_KEY`** 读取凭证
- 当前仓库对应的 Linear 凭证应配置为你提供的那一枚 key；后续若轮换，只更新本地环境，不改本文档

## 当 skill 要求「发布到 issue 跟踪器」

优先在 Linear 的 `cryogrid / 二奢数据分析` 中创建 issue、PRD 对应任务或评论。**正文使用简体中文**，但标签、状态名、字段名保持系统原样。

若需要保存较长的分析草稿、拆解笔记或临时材料，可继续放在 `.scratch/`，但 `.scratch/` 不再作为主 issue tracker。

## 当 skill 要求「获取相关工单」

优先读取用户提供的 Linear issue 标识、标题或项目上下文；若用户同时给出本地 `.scratch/` 路径，则将其视为补充材料而非权威状态源。
