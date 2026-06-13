Status: ready-for-agent

# 构建校验与 Vercel CLI 部署流程

## Parent

`.scratch/luxury-goods-analytics-dashboard/PRD.md`

## What to build

为二奢数据分析仪表盘补齐可重复执行的交付流程，覆盖本地构建校验、运行环境约束与通过 Vercel CLI 的部署动作。该流程应面向终端工作流设计，而不是依赖 Vercel 控制台手工操作。

需要整理并验证构建前置条件，例如依赖安装、Prisma Client 可用、`DATABASE_URL` 存在且使用 Neon pooler 连接串；随后通过 Vercel CLI 完成项目关联、环境变量配置说明、预览部署或正式部署步骤。文档或脚本应让维护者可以从当前分支复现部署。

## Acceptance criteria

- [ ] 明确记录并验证发布前检查项，至少包括依赖安装、Prisma Client 可用、`npm run build` 通过
- [ ] 明确记录 Vercel 运行环境所需的关键环境变量，至少包括 `DATABASE_URL`
- [ ] 部署流程通过 Vercel CLI 执行，而不是要求手工登录控制台点击部署
- [ ] 流程说明可让维护者从当前分支复现一次部署
- [ ] 若构建失败或环境变量缺失，流程会在部署前暴露问题，而不是把错误留到线上

## Blocked by

- `.scratch/luxury-goods-analytics-dashboard/issues/03-pricing-dashboard-ui.md`
