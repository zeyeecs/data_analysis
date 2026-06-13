"use client";

import Link from "next/link";

import { siteConfig } from "../siteConfig";

export default function SettingsPage() {
  return (
    <div className="mt-6 max-w-2xl space-y-8 text-sm text-gray-600 dark:text-gray-400">
      <section>
        <h2 className="text-base font-medium text-gray-900 dark:text-gray-50">数据库连接</h2>
        <p className="mt-2 leading-relaxed">
          前端通过 Prisma 读取 Neon 中的 F / R / V 表。连接串来自仓库根目录{" "}
          <code className="rounded bg-gray-100 px-1 dark:bg-gray-900">database.env</code>{" "}
          或 <code className="rounded bg-gray-100 px-1 dark:bg-gray-900">web/.env.local</code>。
        </p>
        <ul className="mt-3 list-inside list-disc space-y-1">
          <li>
            同步环境变量：在 <code className="rounded bg-gray-100 px-1 dark:bg-gray-900">web/</code>{" "}
            执行 <code className="rounded bg-gray-100 px-1 dark:bg-gray-900">npm run env:sync</code>
          </li>
          <li>须使用 Neon <strong>pooler</strong> 连接地址</li>
          <li>免费实例休眠后首次查询可能需等待数秒</li>
        </ul>
      </section>

      <section>
        <h2 className="text-base font-medium text-gray-900 dark:text-gray-50">本地启动</h2>
        <pre className="mt-2 overflow-x-auto rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs dark:border-gray-800 dark:bg-gray-900">
{`cd web
npm install
npm run env:sync
npm run dev`}
        </pre>
        <p className="mt-2">
          默认地址：{" "}
          <Link href={siteConfig.baseLinks.overview} className="text-indigo-600 dark:text-indigo-400">
            {siteConfig.url}/overview
          </Link>
        </p>
      </section>

      <section>
        <h2 className="text-base font-medium text-gray-900 dark:text-gray-50">关于界面</h2>
        <p className="mt-2 leading-relaxed">
          布局基于 Tremor 开源模板 template-dashboard-oss，已替换为 sjkx 真实数据；
          详情、设置页均为应用内说明，不链接 GitHub。
        </p>
      </section>
    </div>
  );
}
