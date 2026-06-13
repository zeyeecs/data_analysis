import type { CardProps as CategoryBarCardProps } from "@/components/ui/overview/DashboardCategoryBarCard";
import type { CardProps as ProgressBarCardProps } from "@/components/ui/overview/DashboardProgressBarCard";
import type { BreakdownItem, MatchedProduct, ProductAnalysis } from "@/data/schema";
import {
  AvailableChartColors,
  constructCategoryColors,
  getColorClassName,
} from "@/lib/chartUtils";

const QUERY_SCOPE_HINT = "当前搜索关键词与筛选项下的匹配样本";

function compositionScopeHint(analysis: ProductAnalysis): string {
  const { brand, productName } = analysis.filters;
  if (brand && productName) {
    return [brand, productName].filter(Boolean).join(" ");
  }
  return QUERY_SCOPE_HINT;
}

export function toConditionCategoryBarProps(
  analysis: ProductAnalysis,
): Omit<CategoryBarCardProps, "ctaDescription" | "ctaText" | "ctaLink"> | null {
  const items = analysis.breakdownByCondition.filter((i) => i.count > 0);
  if (items.length === 0) return null;

  const colorMap = constructCategoryColors(
    items.map((i) => i.label),
    AvailableChartColors,
  );

  const data = items.map((item) => ({
    title: item.label,
    percentage: item.percentage,
    value: item.count.toLocaleString("zh-CN"),
    color: getColorClassName(colorMap.get(item.label) ?? "gray", "bg"),
  }));

  const total = analysis.conditionBreakdownTotal;
  const hasConditionFilter = (analysis.filters.conditions?.length ?? 0) > 0;
  const productSelected =
    Boolean(analysis.filters.brand) && Boolean(analysis.filters.productName);

  return {
    title: "成色分布",
    change: `Top ${items.length}`,
    value: total.toLocaleString("zh-CN"),
    valueDescription: "条样本",
    subtitle: productSelected
      ? `${compositionScopeHint(analysis)}（不含成色勾选）`
      : hasConditionFilter
        ? "关键词、日期与其它筛选项下（不含成色勾选）"
        : QUERY_SCOPE_HINT,
    data,
  };
}

export function colorDonutScopeHint(analysis: ProductAnalysis): string {
  const { brand, productName } = analysis.filters;
  if (brand && productName) {
    return "当前选中商品";
  }
  return "当前搜索";
}

export function toColorDonutItems(analysis: ProductAnalysis): BreakdownItem[] {
  return analysis.breakdownByColor.filter((i) => i.count > 0);
}

export function toTopProductsProgressCardProps(
  products: MatchedProduct[],
  total: number,
): Omit<ProgressBarCardProps, "ctaDescription" | "ctaText" | "ctaLink"> | null {
  const top = products.slice(0, 5);
  if (top.length === 0 || total <= 0) return null;

  const data = top.map((p) => ({
    title: p.label,
    current: p.sampleCount,
    allowed: total,
    percentage: Math.max(1, Math.round((p.sampleCount / total) * 100)),
    unit: "条",
  }));

  const topSum = top.reduce((s, p) => s + p.sampleCount, 0);

  return {
    title: "匹配商品 Top 5",
    change: QUERY_SCOPE_HINT,
    value: topSum.toLocaleString("zh-CN"),
    valueDescription: `条 · 占搜索范围 ${Math.round((topSum / total) * 100)}%`,
    data,
  };
}
