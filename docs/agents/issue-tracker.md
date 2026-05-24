# Issue 跟踪：本地 Markdown

本仓库的任务与 PRD 以 Markdown 文件形式存放在 `.scratch/`。

## 约定

- 每个功能一个目录：`.scratch/<功能-slug>/`
- PRD 文件：`.scratch/<功能-slug>/PRD.md`
- 实现任务：`.scratch/<功能-slug>/issues/<NN>-<slug>.md`，从 `01` 起编号
- 分诊状态写在每个 issue 文件顶部的 `Status:` 行（标签字符串见 `triage-labels.md`）
- 讨论记录追加在文件末尾的 `## 评论` 标题下

## 当 skill 要求「发布到 issue 跟踪器」

在 `.scratch/<功能-slug>/` 下创建新文件（目录不存在则先创建）。**正文使用简体中文**。

## 当 skill 要求「获取相关工单」

读取用户给出的路径或 issue 编号对应的文件。
