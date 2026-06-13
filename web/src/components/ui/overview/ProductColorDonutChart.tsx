"use client";

import type { BreakdownItem } from "@/data/schema";
import {
  AvailableChartColors,
  chartFillHex,
  constructCategoryColors,
  type AvailableChartColorsKeys,
} from "@/lib/chartUtils";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

type ProductColorDonutChartProps = {
  items: BreakdownItem[];
  total: number;
  /** 样本量旁说明，默认「当前搜索」 */
  scopeHint?: string;
};

type DonutRow = {
  name: string;
  value: number;
  percentage: number;
  fill: string;
};

export function ProductColorDonutChart({
  items,
  total,
  scopeHint = "当前搜索",
}: ProductColorDonutChartProps) {
  const filtered = items.filter((i) => i.count > 0);
  if (filtered.length === 0) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">当前搜索下无颜色数据</p>;
  }

  const colorMap = constructCategoryColors(
    filtered.map((i) => i.label),
    AvailableChartColors,
  );

  const data: DonutRow[] = filtered.map((item) => {
    const key = colorMap.get(item.label) ?? "gray";
    return {
      name: item.label,
      value: item.count,
      percentage: item.percentage,
      fill: chartFillHex[key as AvailableChartColorsKeys],
    };
  });

  return (
    <div>
      <div className="flex items-baseline gap-2">
        <p className="text-xl font-semibold text-gray-900 dark:text-gray-50">
          {total.toLocaleString("zh-CN")}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">条样本 · {scopeHint}</p>
      </div>
      <div className="mt-4 h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="58%"
              outerRadius="88%"
              paddingAngle={filtered.length > 1 ? 2 : 0}
              strokeWidth={0}
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number, _name, props) => {
                const pct = (props.payload as DonutRow).percentage;
                return [`${value.toLocaleString("zh-CN")} 条 (${pct}%)`, "样本"];
              }}
            />
            <Legend
              verticalAlign="bottom"
              height={36}
              formatter={(value) => (
                <span className="text-xs text-gray-700 dark:text-gray-300">{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
