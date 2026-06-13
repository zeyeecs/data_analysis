"use client";

import Link from "next/link";

import { Badge } from "@/components/Badge";
import { useOverview } from "@/providers/OverviewProvider";
import { siteConfig } from "@/app/siteConfig";

const TABLES = [
  {
    id: "F",
    name: "竞品店 F 已售快照",
    desc: "型号字段 model，用于与 R 两两对照分析。",
  },
  {
    id: "R",
    name: "竞品店 R 已售快照",
    desc: "型号字段 model，与 F 并排对照。",
  },
  {
    id: "V",
    name: "竞品店 V 已售快照",
    desc: "商品名 product_name，含 currency、sold_at 等字段。",
  },
] as const;

export default function DetailsPage() {
  const { shops, loading, error } = useOverview();

  return (
    <>
      <h1 className="text-lg font-semibold text-gray-900 sm:text-xl dark:text-gray-50">
        数据详情
      </h1>
      <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
        本仪表盘仅连接仓库 Neon 数据库，不跳转外部 Git 或第三方页面。
      </p>

      {loading ? (
        <p className="mt-8 text-gray-500">加载中…</p>
      ) : error ? (
        <p className="mt-8 text-red-500">{error}</p>
      ) : (
        <div className="mt-8 space-y-6">
          <section className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <h2 className="font-medium text-gray-900 dark:text-gray-50">记录规模</h2>
            <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-gray-50">
              {shops ? shops.total.toLocaleString("zh-CN") : "—"}
              <span className="ml-2 text-sm font-normal text-gray-500">条已售记录</span>
            </p>
            {shops ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant="neutral">F: {shops.F.toLocaleString("zh-CN")}</Badge>
                <Badge variant="neutral">R: {shops.R.toLocaleString("zh-CN")}</Badge>
                <Badge variant="neutral">V: {shops.V.toLocaleString("zh-CN")}</Badge>
              </div>
            ) : null}
          </section>

          <section>
            <h2 className="font-medium text-gray-900 dark:text-gray-50">数据表说明</h2>
            <ul className="mt-4 space-y-4">
              {TABLES.map((table) => (
                <li
                  key={table.id}
                  className="rounded-lg border border-gray-200 p-4 dark:border-gray-800"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-indigo-600 dark:text-indigo-400">
                      {table.id}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-gray-50">
                      {table.name}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{table.desc}</p>
                </li>
              ))}
            </ul>
          </section>

          <p className="text-sm text-gray-500">
            查看趋势图请返回{" "}
            <Link
              href={siteConfig.baseLinks.overview}
              className="text-indigo-600 underline dark:text-indigo-400"
            >
              概览
            </Link>
            。
          </p>
        </div>
      )}
    </>
  );
}
