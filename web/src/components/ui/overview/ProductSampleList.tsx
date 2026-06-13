"use client";

import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/Dialog";
import type { ProductSample, ProductSamplesResult } from "@/data/schema";
import { formatCondition } from "@/lib/condition";
import { cx, formatters } from "@/lib/utils";
import { RiArrowDownSLine, RiArrowUpSLine, RiImageLine } from "@remixicon/react";
import React from "react";

export type ProductSampleQuery = {
  q: string;
  colors: string[];
  excludeColors: string[];
  conditions: string[];
  excludeConditions: string[];
  materials: string[];
  excludeMaterials: string[];
  years: string[];
  excludeYears: string[];
  shops: string[];
  start: string;
  end: string;
  brand?: string;
  product?: string;
};

type ProductSampleListProps = {
  query: ProductSampleQuery;
  totalSamples: number;
  scopeLabel?: string;
};

const PAGE_SIZE = 20;

function buildSearchParams(query: ProductSampleQuery, page: number) {
  const params = new URLSearchParams();
  params.set("q", query.q.trim());
  for (const color of query.colors) {
    if (color) params.append("color", color);
  }
  for (const color of query.excludeColors) {
    if (color) params.append("excludeColor", color);
  }
  for (const condition of query.conditions) {
    if (condition) params.append("condition", condition);
  }
  for (const condition of query.excludeConditions) {
    if (condition) params.append("excludeCondition", condition);
  }
  for (const material of query.materials) {
    if (material) params.append("material", material);
  }
  for (const material of query.excludeMaterials) {
    if (material) params.append("excludeMaterial", material);
  }
  for (const year of query.years) {
    if (year) params.append("year", year);
  }
  for (const year of query.excludeYears) {
    if (year) params.append("excludeYear", year);
  }
  for (const shop of query.shops) {
    if (shop) params.append("shop", shop);
  }
  if (query.start) params.set("start", query.start);
  if (query.end) params.set("end", query.end);
  if (query.brand) params.set("brand", query.brand);
  if (query.product) params.set("product", query.product);
  params.set("page", String(page));
  params.set("pageSize", String(PAGE_SIZE));
  return params;
}

function SampleImage({ url, label }: { url: string | null; label: string }) {
  const [failed, setFailed] = React.useState(false);

  if (!url || failed) {
    return (
      <div
        className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md border border-dashed border-gray-200 bg-gray-50 text-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-500"
        aria-hidden
      >
        <RiImageLine className="h-5 w-5" />
      </div>
    );
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          className="cursor-zoom-in rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-gray-950"
          aria-label={`查看大图：${label}`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={label}
            loading="lazy"
            onError={() => setFailed(true)}
            className="h-14 w-14 shrink-0 rounded-md border border-gray-200 object-cover dark:border-gray-700"
          />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-[min(92vw,48rem)] border-0 bg-transparent p-2 shadow-none sm:p-4">
        <DialogTitle className="sr-only">{label}</DialogTitle>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt={label} className="max-h-[85vh] w-full rounded-lg object-contain" />
      </DialogContent>
    </Dialog>
  );
}

function SampleRow({ sample }: { sample: ProductSample }) {
  return (
    <tr className="border-t border-gray-100 dark:border-gray-800">
      <td className="px-4 py-3">
        <SampleImage url={sample.imageUrl} label={sample.label} />
      </td>
      <td className="py-3 pr-3 text-sm text-gray-600 dark:text-gray-300">{sample.shop}</td>
      <td className="py-3 pr-3">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-50">{sample.label}</p>
        {sample.itemId ? (
          <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">ID {sample.itemId}</p>
        ) : null}
      </td>
      <td className="py-3 pr-3 text-sm text-gray-600 dark:text-gray-300">
        {formatCondition(sample.condition) ?? "—"}
      </td>
      <td className="py-3 pr-3 text-sm text-gray-600 dark:text-gray-300">{sample.color ?? "—"}</td>
      <td className="py-3 pr-3 text-sm font-medium text-gray-900 dark:text-gray-50">
        {formatters.currency(sample.price, "CNY")}
      </td>
      <td className="py-3 pr-3 text-sm text-gray-600 dark:text-gray-300">{sample.snapshotDate}</td>
    </tr>
  );
}

export function ProductSampleList({ query, totalSamples, scopeLabel }: ProductSampleListProps) {
  const [expanded, setExpanded] = React.useState(false);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ProductSamplesResult | null>(null);

  const queryKey = React.useMemo(
    () =>
      [
        query.q,
        query.colors.join("\0"),
        query.excludeColors.join("\0"),
        query.conditions.join("\0"),
        query.excludeConditions.join("\0"),
        query.materials.join("\0"),
        query.excludeMaterials.join("\0"),
        query.years.join("\0"),
        query.excludeYears.join("\0"),
        query.shops.join("\0"),
        query.start,
        query.end,
        query.brand ?? "",
        query.product ?? "",
      ].join("\0"),
    [query],
  );

  React.useEffect(() => {
    setPage(1);
    setResult(null);
    setError(null);
    setExpanded(false);
  }, [queryKey]);

  React.useEffect(() => {
    if (!expanded) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const params = buildSearchParams(query, page);
        const res = await fetch(`/api/product-samples?${params}`);
        const json = await res.json();
        if (!res.ok) throw new Error(json.error ?? "加载样本失败");
        if (cancelled) return;
        setResult(json as ProductSamplesResult);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载样本失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [expanded, page, query]);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1;
  const canPaginate = expanded && result && result.total > PAGE_SIZE;

  return (
    <section className="mt-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-50">样本明细</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {scopeLabel ? `${scopeLabel} · ` : ""}
            共 {totalSamples.toLocaleString("zh-CN")} 条有价样本
            {expanded ? "，每页 20 条" : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className={cx(
            "inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-sm font-medium transition",
            expanded
              ? "border-indigo-500 bg-indigo-50 text-indigo-900 dark:border-indigo-400 dark:bg-indigo-950 dark:text-indigo-100"
              : "border-gray-200 bg-white text-gray-800 hover:border-gray-300 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-200 dark:hover:border-gray-700",
          )}
        >
          {expanded ? (
            <>
              收起列表
              <RiArrowUpSLine className="h-4 w-4" />
            </>
          ) : (
            <>
              点击展开样本列表
              <RiArrowDownSLine className="h-4 w-4" />
            </>
          )}
        </button>
      </div>

      {expanded ? (
        <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-800">
          {loading && !result ? (
            <p className="p-4 text-sm text-gray-500 dark:text-gray-400">正在加载样本…</p>
          ) : error ? (
            <p className="p-4 text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : result && result.items.length === 0 ? (
            <p className="p-4 text-sm text-gray-500 dark:text-gray-400">暂无匹配样本。</p>
          ) : result ? (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                      <th className="px-4 py-3">图片</th>
                      <th className="py-3 pr-3">渠道</th>
                      <th className="py-3 pr-3">商品</th>
                      <th className="py-3 pr-3">成色</th>
                      <th className="py-3 pr-3">颜色</th>
                      <th className="py-3 pr-3">价格</th>
                      <th className="py-3 pr-3">快照日期</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.map((sample) => (
                      <SampleRow
                        key={`${sample.shop}-${sample.itemId ?? sample.label}-${sample.snapshotDate}-${sample.price}`}
                        sample={sample}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 px-4 py-3 dark:border-gray-800">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  第 {result.page} / {totalPages} 页，共 {result.total.toLocaleString("zh-CN")} 条
                </p>
                {canPaginate ? (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={page <= 1 || loading}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      className="rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-700 transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:border-gray-600"
                    >
                      上一页
                    </button>
                    <button
                      type="button"
                      disabled={page >= totalPages || loading}
                      onClick={() => setPage((p) => p + 1)}
                      className="rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-700 transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:border-gray-600"
                    >
                      下一页
                    </button>
                  </div>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
