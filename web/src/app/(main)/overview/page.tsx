"use client";

import { CategoryBarCard } from "@/components/ui/overview/DashboardCategoryBarCard";
import { ProgressBarCard } from "@/components/ui/overview/DashboardProgressBarCard";
import { ProductMatchList } from "@/components/ui/overview/ProductMatchList";
import { ProductSampleList } from "@/components/ui/overview/ProductSampleList";
import { ProductPriceTrendChart } from "@/components/ui/overview/ProductPriceTrendChart";
import { ProductSearchBar } from "@/components/ui/overview/ProductSearchBar";
import type { AttributeFilterSelection, MatchedProduct } from "@/data/schema";

const emptyAttributeFilter = (): AttributeFilterSelection => ({ include: [], exclude: [] });
import { ProductColorDonutChart } from "@/components/ui/overview/ProductColorDonutChart";
import {
  colorDonutScopeHint,
  toColorDonutItems,
  toConditionCategoryBarProps,
  toTopProductsProgressCardProps,
} from "@/lib/overview-breakdown-cards";
import { buildRecentDayRange } from "@/lib/dates";
import { formatters } from "@/lib/utils";
import { useOverview } from "@/providers/OverviewProvider";
import { format } from "date-fns";
import React from "react";
import { DateRange } from "react-day-picker";

const priceFmt = (value: number | null) =>
  value != null ? formatters.currency(value, "CNY") : "—";

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-50">{value}</p>
      {hint ? <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{hint}</p> : null}
    </div>
  );
}

export default function Overview() {
  const { analysis, filterOptions, shops: shopTotals, loading, analyzing, error, runAnalysis } =
    useOverview();

  const [keywords, setKeywords] = React.useState("");
  const [colorFilter, setColorFilter] = React.useState<AttributeFilterSelection>(emptyAttributeFilter);
  const [conditionFilter, setConditionFilter] = React.useState<AttributeFilterSelection>(
    emptyAttributeFilter,
  );
  const [materialFilter, setMaterialFilter] = React.useState<AttributeFilterSelection>(
    emptyAttributeFilter,
  );
  const [yearFilter, setYearFilter] = React.useState<AttributeFilterSelection>(emptyAttributeFilter);
  const [shops, setShops] = React.useState<string[]>([]);
  const [selectedDates, setSelectedDates] = React.useState<DateRange | undefined>(() =>
    buildRecentDayRange(90),
  );
  const [selectedProduct, setSelectedProduct] = React.useState<MatchedProduct | null>(null);
  const [matchedProducts, setMatchedProducts] = React.useState<MatchedProduct[]>([]);

  const runQuery = React.useCallback(
    (product: MatchedProduct | null) => {
      const start = selectedDates?.from ? format(selectedDates.from, "yyyy-MM-dd") : "";
      const end = selectedDates?.to ? format(selectedDates.to, "yyyy-MM-dd") : "";
      void runAnalysis({
        q: keywords,
        colors: colorFilter.include,
        excludeColors: colorFilter.exclude,
        conditions: conditionFilter.include,
        excludeConditions: conditionFilter.exclude,
        materials: materialFilter.include,
        excludeMaterials: materialFilter.exclude,
        years: yearFilter.include,
        excludeYears: yearFilter.exclude,
        shops,
        start,
        end,
        brand: product?.brand,
        product: product?.productName,
      });
    },
    [
      keywords,
      colorFilter,
      conditionFilter,
      materialFilter,
      yearFilter,
      shops,
      selectedDates,
      runAnalysis,
    ],
  );

  const handleAnalyze = React.useCallback(() => {
    setSelectedProduct(null);
    setMatchedProducts([]);
    runQuery(null);
  }, [runQuery]);

  const handleSelectProduct = React.useCallback(
    (product: MatchedProduct | null) => {
      setSelectedProduct(product);
      runQuery(product);
    },
    [runQuery],
  );

  React.useEffect(() => {
    if (!analysis) {
      setSelectedProduct(null);
      setMatchedProducts([]);
      return;
    }
    if (analysis.products.length > 0) {
      setMatchedProducts(analysis.products);
    }
    const { brand, productName } = analysis.filters;
    if (!brand || !productName) {
      setSelectedProduct(null);
      return;
    }
    const match = analysis.products.find(
      (p) => p.brand === brand && p.productName === productName,
    );
    setSelectedProduct(
      match ?? {
        brand,
        productName,
        label: [brand, productName].filter(Boolean).join(" "),
        sampleCount: analysis.summary.sampleCount,
        shops: [],
      },
    );
  }, [analysis]);

  const sampleQuery = React.useMemo(
    () => ({
      q: keywords,
      colors: colorFilter.include,
      excludeColors: colorFilter.exclude,
      conditions: conditionFilter.include,
      excludeConditions: conditionFilter.exclude,
      materials: materialFilter.include,
      excludeMaterials: materialFilter.exclude,
      years: yearFilter.include,
      excludeYears: yearFilter.exclude,
      shops,
      start: selectedDates?.from ? format(selectedDates.from, "yyyy-MM-dd") : "",
      end: selectedDates?.to ? format(selectedDates.to, "yyyy-MM-dd") : "",
      brand: selectedProduct?.brand,
      product: selectedProduct?.productName,
    }),
    [
      keywords,
      colorFilter,
      conditionFilter,
      materialFilter,
      yearFilter,
      shops,
      selectedDates,
      selectedProduct,
    ],
  );

  if (loading) {
    return <p className="text-gray-500 dark:text-gray-400">正在连接数据库…</p>;
  }

  if (error && !analysis) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
        <p className="font-medium">数据库连接失败</p>
        <p className="mt-2 text-sm">{error}</p>
        <p className="mt-2 text-sm">
          请检查 database.env，并在 web/ 目录执行 npm run env:sync。
        </p>
      </div>
    );
  }

  const summary = analysis?.summary;
  const colorDonutItems = analysis ? toColorDonutItems(analysis) : [];
  const conditionBarProps = analysis ? toConditionCategoryBarProps(analysis) : null;
  const queryScopeTotal = analysis?.queryScopeSampleCount ?? 0;
  const colorBreakdownTotal = analysis?.colorBreakdownTotal ?? queryScopeTotal;
  const topProductsProps =
    analysis && queryScopeTotal > 0
      ? toTopProductsProgressCardProps(analysis.products, queryScopeTotal)
      : null;
  const showComposition =
    colorDonutItems.length > 0 || conditionBarProps != null || topProductsProps != null;

  // 日期选择器使用库内快照边界，勿用 trend 首尾（否则会锁死在当前关键词有数据的日期）
  const pickerMinDate = shopTotals?.snapshotDates?.min
    ? new Date(`${shopTotals.snapshotDates.min}T00:00:00`)
    : buildRecentDayRange(365).from!;
  const pickerMaxDate = shopTotals?.snapshotDates?.max
    ? new Date(`${shopTotals.snapshotDates.max}T00:00:00`)
    : new Date();

  return (
    <>
      <section>
        <h1 className="text-lg font-semibold text-gray-900 sm:text-xl dark:text-gray-50">
          商品分析
        </h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          跨 F / R / V 全渠道聚合；关键词可留空以分析当前日期与筛选项下的全部商品。
          {shopTotals ? ` 库内共 ${shopTotals.total.toLocaleString("zh-CN")} 条已售记录。` : null}
        </p>

        <div className="sticky top-16 z-20 mt-6 overflow-visible rounded-xl border border-gray-200 bg-white p-4 shadow-sm lg:top-0 dark:border-gray-800 dark:bg-gray-950">
          <ProductSearchBar
            keywords={keywords}
            colorFilter={colorFilter}
            conditionFilter={conditionFilter}
            materialFilter={materialFilter}
            yearFilter={yearFilter}
            shops={shops}
            selectedDates={selectedDates}
            filterOptions={filterOptions}
            analyzing={analyzing}
            minDate={pickerMinDate}
            maxDate={pickerMaxDate}
            onKeywordsChange={setKeywords}
            onColorFilterChange={setColorFilter}
            onConditionFilterChange={setConditionFilter}
            onMaterialFilterChange={setMaterialFilter}
            onYearFilterChange={setYearFilter}
            onShopsChange={setShops}
            onDatesChange={setSelectedDates}
            onAnalyze={handleAnalyze}
          />
        </div>
      </section>

      {error && analysis ? (
        <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>
      ) : null}

      {!analysis ? (
        <p className="mt-10 text-sm text-gray-500 dark:text-gray-400">
          点击「开始分析」查看价格数据；可输入关键词缩小范围，留空则分析表内全部匹配记录。
        </p>
      ) : summary?.sampleCount === 0 ? (
        <p className="mt-10 text-sm text-gray-500 dark:text-gray-400">
          未找到匹配记录，请调整关键词、日期或筛选条件。
        </p>
      ) : (
        <>
          {(analysis.matchedProductCount ?? 0) > 0 ? (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-gray-900 dark:text-gray-50">
                匹配商品
              </h2>
              <div className="mt-2 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
                <ProductMatchList
                  products={matchedProducts}
                  totalProductCount={analysis.matchedProductCount}
                  selectedBrand={selectedProduct?.brand ?? null}
                  selectedProductName={selectedProduct?.productName ?? null}
                  onSelect={handleSelectProduct}
                />
              </div>
            </section>
          ) : null}

          <section className="mt-8">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-50">
              {selectedProduct ? `${selectedProduct.label} · 价格概览` : "价格概览"}
            </h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                label="样本量"
                value={summary!.sampleCount.toLocaleString("zh-CN")}
                hint="匹配且已录入价格的已售记录数"
              />
              <KpiCard label="均价" value={priceFmt(summary!.avgPrice)} />
              <KpiCard label="最低价" value={priceFmt(summary!.minPrice)} />
              <KpiCard label="最高价" value={priceFmt(summary!.maxPrice)} />
            </div>
          </section>

          <ProductSampleList
            query={sampleQuery}
            totalSamples={summary!.sampleCount}
            scopeLabel={selectedProduct?.label}
          />

          {showComposition ? (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-gray-900 dark:text-gray-50">
                样本构成
              </h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                {selectedProduct
                  ? "颜色与成色仅统计当前选中商品；Top 5 仍为当前搜索范围"
                  : "分布图在对应维度上不含该维度的勾选；Top 5 基于当前关键词与全部筛选项"}
              </p>
              <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
                {colorDonutItems.length > 0 ? (
                  <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-50">
                      颜色占比
                    </h3>
                    <ProductColorDonutChart
                      items={colorDonutItems}
                      total={colorBreakdownTotal}
                      scopeHint={analysis ? colorDonutScopeHint(analysis) : "当前搜索"}
                    />
                  </div>
                ) : null}
                {conditionBarProps ? (
                  <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
                    <CategoryBarCard {...conditionBarProps} />
                  </div>
                ) : null}
                {topProductsProps ? (
                  <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
                    <ProgressBarCard {...topProductsProps} />
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          <section className="mt-10">
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-50">
              {selectedProduct ? `${selectedProduct.label} · 价格趋势` : "价格趋势"}
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              仅展示有成交快照的日期；均价、最低价、最高价（不区分店铺）
            </p>
            <div className="mt-4 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
              <ProductPriceTrendChart trend={analysis.trend} selectedDates={selectedDates} />
            </div>
          </section>
        </>
      )}
    </>
  );
}
