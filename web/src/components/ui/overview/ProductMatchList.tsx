"use client";

import type { MatchedProduct } from "@/data/schema";
import { cx } from "@/lib/utils";

type ProductMatchListProps = {
  products: MatchedProduct[];
  /** 匹配到的商品款数；可与 products 长度不同（列表仅展示 Top 200） */
  totalProductCount: number;
  selectedBrand: string | null;
  selectedProductName: string | null;
  onSelect: (product: MatchedProduct | null) => void;
};

export function ProductMatchList({
  products,
  totalProductCount,
  selectedBrand,
  selectedProductName,
  onSelect,
}: ProductMatchListProps) {
  const allSelected = !selectedBrand && !selectedProductName;

  return (
    <div className="mt-4">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        共 {totalProductCount.toLocaleString("zh-CN")} 款商品，点击选择查看该款价格趋势
        {totalProductCount > products.length ? (
          <span className="text-gray-400 dark:text-gray-500">
            {" "}
            （列表展示样本量 Top {products.length.toLocaleString("zh-CN")}）
          </span>
        ) : null}
      </p>
      <ul className="mt-3 flex max-h-64 flex-col gap-2 overflow-y-auto pr-1">
        <li>
          <button
            type="button"
            onClick={() => onSelect(null)}
            className={cx(
              "w-full rounded-lg border px-3 py-2.5 text-left text-sm transition",
              allSelected
                ? "border-indigo-500 bg-indigo-50 text-indigo-900 dark:border-indigo-400 dark:bg-indigo-950 dark:text-indigo-100"
                : "border-gray-200 bg-white text-gray-800 hover:border-gray-300 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-200 dark:hover:border-gray-700",
            )}
          >
            <span className="font-medium">全部匹配商品</span>
            <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">
              合并所有匹配结果
            </span>
          </button>
        </li>
        {products.map((product) => {
          const selected =
            selectedBrand === product.brand && selectedProductName === product.productName;
          return (
            <li key={`${product.brand}\0${product.productName}`}>
              <button
                type="button"
                onClick={() => onSelect(product)}
                className={cx(
                  "w-full rounded-lg border px-3 py-2.5 text-left text-sm transition",
                  selected
                    ? "border-indigo-500 bg-indigo-50 text-indigo-900 dark:border-indigo-400 dark:bg-indigo-950 dark:text-indigo-100"
                    : "border-gray-200 bg-white text-gray-800 hover:border-gray-300 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-200 dark:hover:border-gray-700",
                )}
              >
                <span className="font-medium">{product.label}</span>
                <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">
                  {product.sampleCount.toLocaleString("zh-CN")} 条有价样本
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
