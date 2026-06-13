import type { BreakdownItem } from "@/data/schema";

/** 展示用：trim 后原样返回，不做档位映射。 */
export function formatCondition(value: string | null | undefined): string | null {
  const text = value?.trim();
  return text || null;
}

/** 按 count 降序展示成色分布（标签保持库内原始值）。 */
export function sortConditionBreakdown(items: BreakdownItem[]): BreakdownItem[] {
  return [...items].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh-CN"));
}
