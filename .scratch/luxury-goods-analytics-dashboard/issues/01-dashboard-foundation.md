Status: ready-for-agent

# 仪表盘基础设施与依赖收敛

## Parent

`.scratch/luxury-goods-analytics-dashboard/PRD.md`

## What to build

在现有 `web/` Next.js 应用内补齐二奢数据分析仪表盘所需的前端与数据访问基础设施，形成一个可继续承载定价分析功能的稳定底座。

本切片重点不是交付完整业务页面，而是把运行环境收紧到 PRD 约定的技术栈：Next.js App Router、TypeScript、Tailwind CSS、Tremor UI、Prisma、Neon pooler 连接。需要确认或补齐依赖安装、基础样式管线、Prisma 初始化方式和必要的环境变量约束，并消除当前 `web/` 中与目标实现冲突的数据库访问路径。

交付完成后，仓库应具备继续实现分析服务与仪表盘页面的前提条件，且 `npm run build` 可以在未部署前作为可靠门槛使用。

## Acceptance criteria

- [ ] `web/` 已安装并声明仪表盘所需核心依赖：Tremor UI、Prisma、Prisma Client，以及必要的样式依赖
- [ ] Tailwind CSS 基础样式管线已就绪，能够支撑 Tremor 组件与自定义页面样式
- [ ] 存在可复用的 Prisma Client singleton 初始化模块，并符合 serverless / 开发热重载场景
- [ ] 数据库连接约束已文档化或配置化：`DATABASE_URL` 使用 Neon pooler 连接串
- [ ] `npm run build` 可通过，且不会因为缺失基础设施而阻塞后续切片

## Blocked by

None - can start immediately
